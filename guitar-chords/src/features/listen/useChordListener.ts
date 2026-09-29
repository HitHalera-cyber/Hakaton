// Прослушивание гитары через микрофон. Два режима:
//  • «По удару» — после каждого удара по струнам аккорд распознаётся за ~0,5 с;
//  • «Держите аккорд» — звук копится несколько секунд, и выдаётся один уверенный результат
//    (точнее при тихой игре и шуме; повторные удары того же аккорда не сбрасывают отсчёт).
// Живёт на уровне приложения, чтобы слушать можно было на любой вкладке.

import { useEffect, useMemo, useRef, useState } from 'react';
import { useStored } from '../../app/useStored';
import { audio } from '../../core/audio/engine';
import { LIVE_VOCAB, buildModels, recognizeChord, type Recognition, type RecognizedChord } from '../../core/analysis/chordRecognition';
import { SpectrumAnalyzer } from '../../core/analysis/dsp';

/** Окно анализа ~0,34 с: достаточно, чтобы различать соседние полутоны в басу. */
const FRAME = 16384;
/** Режим «по удару»: когда начинать анализ после удара и сколько слушать. */
const START_AFTER = 0.36;
const LISTEN_FOR = 1.8;

export type ListenMode = 'strum' | 'hold';

export interface ListenSettings {
  mode: ListenMode;
  /** Усиление микрофона (×). */
  gain: number;
  /** Сколько держать аккорд в режиме «Держите аккорд», секунды. */
  holdSeconds: number;
  sensitivity: number;
  showOnBoard: boolean;
}

const DEFAULTS: ListenSettings = { mode: 'strum', gain: 3, holdSeconds: 2.5, sensitivity: 0.5, showOnBoard: true };

export type HoldState = 'idle' | 'listening' | 'done' | 'short';

export function useChordListener(onChord: (chord: RecognizedChord) => void) {
  const [settings, setSettings] = useStored<ListenSettings>('gc.listen', DEFAULTS);
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [level, setLevel] = useState(0);
  const [result, setResult] = useState<Recognition | null>(null);
  const [chroma, setChroma] = useState<number[]>(new Array(12).fill(0));
  const [history, setHistory] = useState<RecognizedChord[]>([]);
  const [hold, setHold] = useState<{ state: HoldState; progress: number }>({ state: 'idle', progress: 0 });

  const models = useMemo(() => buildModels(LIVE_VOCAB), []);
  const stream = useRef<MediaStream | null>(null);
  const gainNode = useRef<GainNode | null>(null);
  const raf = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const opts = useRef({ settings, onChord });
  opts.current = { settings, onChord };

  useEffect(() => {
    if (gainNode.current) gainNode.current.gain.value = settings.gain;
  }, [settings.gain]);

  const stop = () => {
    if (raf.current) cancelAnimationFrame(raf.current);
    raf.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    analyserRef.current = null;
    gainNode.current = null;
    setActive(false);
    setLevel(0);
    setHold({ state: 'idle', progress: 0 });
  };
  useEffect(() => stop, []);

  const start = async () => {
    setError('');
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      stream.current = s;
      const ctx = audio.context;
      const src = ctx.createMediaStreamSource(s);
      const gain = ctx.createGain();
      gain.gain.value = opts.current.settings.gain;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = FRAME;
      src.connect(gain).connect(analyser);
      gainNode.current = gain;
      analyserRef.current = analyser;
      setActive(true);

      const spectrum = new SpectrumAnalyzer(FRAME, ctx.sampleRate);
      const buf = new Float32Array(analyser.fftSize);
      const acc = { chroma: new Float32Array(12), bass: new Float32Array(12), frames: 0 };
      const resetAcc = () => {
        acc.chroma.fill(0);
        acc.bass.fill(0);
        acc.frames = 0;
      };
      const addFrame = () => {
        const f = spectrum.frame(buf, buf.length - FRAME);
        for (let i = 0; i < 12; i++) {
          acc.chroma[i] += f.chroma[i];
          acc.bass[i] += f.bass[i];
        }
        acc.frames++;
        const r = recognizeChord(acc.chroma, acc.bass, models);
        const max = Math.max(...acc.chroma) || 1;
        setChroma([...acc.chroma].map((v) => v / max));
        return r;
      };
      const emit = (chord: RecognizedChord) => {
        setHistory((h) => [chord, ...h].slice(0, 16));
        opts.current.onChord(chord);
      };

      let floor = 0.001;
      let onsetAt = -10;
      let lastFrameAt = 0;
      let lastSymbol = '';
      const recent: { t: number; rms: number }[] = [];
      // Режим «держите аккорд».
      let holdStart = -1;
      let lastSoundAt = -10;
      let emitted = false;

      const loop = () => {
        const an = analyserRef.current;
        if (!an) return;
        const { mode, sensitivity, holdSeconds } = opts.current.settings;
        an.getFloatTimeDomainData(buf);
        // Громкость последних ~40 мс.
        let sum = 0;
        for (let i = buf.length - 2048; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / 2048);
        setLevel(Math.min(1, rms * 6));
        const now = ctx.currentTime;

        // Удар — резкий скачок громкости: затухающий аккорд тоже громче фона, но не растёт.
        const threshold = 3.5 - sensitivity * 2.2; // во сколько раз громче фона
        const jump = 2.2 - sensitivity * 0.8; // во сколько раз громче, чем мгновение назад
        while (recent.length && recent[0].t < now - 0.25) recent.shift();
        const before = recent.filter((r) => r.t < now - 0.03);
        const recentMin = before.length ? Math.min(...before.map((r) => r.rms)) : 0;
        recent.push({ t: now, rms });
        const onset = rms > Math.max(0.002, floor * threshold) && rms > recentMin * jump && now - onsetAt > 0.25;
        if (onset) onsetAt = now;
        else if (rms < floor * 2) floor = floor * 0.97 + rms * 0.03;

        if (mode === 'strum') {
          if (onset) resetAcc();
          const since = now - onsetAt;
          if (since > START_AFTER && since < LISTEN_FOR && now - lastFrameAt > 0.09 && rms > floor * 1.5) {
            lastFrameAt = now;
            const r = addFrame();
            setResult(r);
            // Аккорд «услышан», когда накопилось хотя бы 2 кадра.
            if (r.best && acc.frames >= 2 && r.best.symbol !== lastSymbol) {
              lastSymbol = r.best.symbol;
              emit(r.best);
            }
          }
        } else {
          const sounding = rms > Math.max(0.0015, floor * 2.2);
          if (sounding) lastSoundAt = now;
          // Новый аккорд после уже выданного результата — начинаем заново.
          if (onset && emitted) {
            holdStart = -1;
            emitted = false;
          }
          if (sounding && holdStart < 0) {
            holdStart = now;
            emitted = false;
            resetAcc();
          }
          if (holdStart >= 0 && !emitted) {
            const held = now - holdStart;
            // Первые 0,25 с — сам удар, он шумный.
            if (held > 0.25 && now - lastFrameAt > 0.1 && sounding) {
              lastFrameAt = now;
              setResult(addFrame());
            }
            const progress = Math.min(1, held / holdSeconds);
            setHold({ state: 'listening', progress });
            if (progress >= 1 && acc.frames >= 3) {
              const r = recognizeChord(acc.chroma, acc.bass, models);
              setResult(r);
              emitted = true;
              setHold({ state: 'done', progress: 1 });
              if (r.best) emit(r.best);
            }
          }
          // Тишина — сброс; если держали слишком мало, подсказываем.
          if (holdStart >= 0 && now - lastSoundAt > 0.5) {
            if (!emitted) setHold({ state: 'short', progress: 0 });
            holdStart = -1;
            emitted = false;
          }
        }
        raf.current = requestAnimationFrame(loop);
      };
      loop();
    } catch (e) {
      setError(
        e instanceof Error && e.name === 'NotAllowedError'
          ? 'Нет доступа к микрофону. В Windows: Параметры → Конфиденциальность → Микрофон → разрешить приложениям доступ.'
          : 'Не удалось включить микрофон: ' + (e instanceof Error ? e.message : String(e)),
      );
      stop();
    }
  };

  return {
    active,
    error,
    level,
    result,
    chroma,
    history,
    hold,
    clearHistory: () => setHistory([]),
    settings,
    patch: (p: Partial<ListenSettings>) => setSettings((s) => ({ ...s, ...p })),
    showOnBoard: settings.showOnBoard,
    start: () => void start(),
    stop,
  };
}

export type ChordListener = ReturnType<typeof useChordListener>;
