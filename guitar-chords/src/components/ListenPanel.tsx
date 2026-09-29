import { useEffect, useMemo, useRef, useState } from 'react';
import { audio } from '../audio/engine';
import { LIVE_VOCAB, buildModels, recognizeChord, type RecognizedChord } from '../music/chordRecognition';
import { SpectrumAnalyzer } from '../music/dsp';
import { pcName } from '../music/notes';

interface Props {
  onChord: (chord: RecognizedChord) => void;
}

/** Окно анализа ~0,34 с: достаточно, чтобы различать соседние полутоны в басу. */
const FRAME = 16384;
/** Через сколько после удара начинаем анализ (окно должно целиком попасть на новый аккорд) и сколько слушаем. */
const START_AFTER = 0.36;
const LISTEN_FOR = 1.8;

export function ListenPanel({ onChord }: Props) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [level, setLevel] = useState(0);
  const [result, setResult] = useState<{ best: RecognizedChord | null; alternatives: RecognizedChord[] } | null>(null);
  const [chroma, setChroma] = useState<number[]>(new Array(12).fill(0));
  const [history, setHistory] = useState<RecognizedChord[]>([]);
  const [showOnBoard, setShowOnBoard] = useState(true);
  const [sensitivity, setSensitivity] = useState(0.5);

  const models = useMemo(() => buildModels(LIVE_VOCAB), []);
  const stream = useRef<MediaStream | null>(null);
  const raf = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const opts = useRef({ showOnBoard, sensitivity, onChord });
  opts.current = { showOnBoard, sensitivity, onChord };

  const stop = () => {
    if (raf.current) cancelAnimationFrame(raf.current);
    raf.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    analyserRef.current = null;
    setActive(false);
    setLevel(0);
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
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 16384;
      src.connect(analyser);
      analyserRef.current = analyser;
      setActive(true);

      const spectrum = new SpectrumAnalyzer(FRAME, ctx.sampleRate);
      const buf = new Float32Array(analyser.fftSize);
      let floor = 0.003;
      let onsetAt = -10;
      const recent: { t: number; rms: number }[] = [];
      let lastFrameAt = 0;
      const acc = { chroma: new Float32Array(12), bass: new Float32Array(12), frames: 0 };
      let lastSymbol = '';

      const loop = () => {
        const an = analyserRef.current;
        if (!an) return;
        an.getFloatTimeDomainData(buf);
        // Громкость последних ~40 мс — для поиска удара по струнам.
        let sum = 0;
        for (let i = buf.length - 2048; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / 2048);
        setLevel(Math.min(1, rms * 10));
        const now = ctx.currentTime;
        const threshold = 3.5 - opts.current.sensitivity * 2.2; // во сколько раз громче фона
        const jump = 2.2 - opts.current.sensitivity * 0.8; // во сколько раз громче, чем мгновение назад
        // Удар — резкий скачок громкости: затухающий аккорд тоже громче фона, но не растёт.
        while (recent.length && recent[0].t < now - 0.25) recent.shift();
        const before = recent.filter((r) => r.t < now - 0.03);
        const recentMin = before.length ? Math.min(...before.map((r) => r.rms)) : 0;
        recent.push({ t: now, rms });

        if (rms > Math.max(0.006, floor * threshold) && rms > recentMin * jump && now - onsetAt > 0.25) {
          onsetAt = now;
          acc.chroma.fill(0);
          acc.bass.fill(0);
          acc.frames = 0;
        } else if (rms < floor * 2) {
          floor = floor * 0.97 + rms * 0.03;
        }

        const since = now - onsetAt;
        if (since > START_AFTER && since < LISTEN_FOR && now - lastFrameAt > 0.09 && rms > floor * 1.5) {
          lastFrameAt = now;
          const f = spectrum.frame(buf, buf.length - FRAME);
          for (let i = 0; i < 12; i++) {
            acc.chroma[i] += f.chroma[i];
            acc.bass[i] += f.bass[i];
          }
          acc.frames++;
          const r = recognizeChord(acc.chroma, acc.bass, models);
          const max = Math.max(...acc.chroma) || 1;
          setChroma([...acc.chroma].map((v) => v / max));
          setResult(r);
          // Аккорд считаем «услышанным», когда накопилось хотя бы 2 кадра.
          if (r.best && acc.frames >= 2 && r.best.symbol !== lastSymbol) {
            lastSymbol = r.best.symbol;
            const chord = r.best;
            setHistory((h) => [chord, ...h].slice(0, 16));
            if (opts.current.showOnBoard) opts.current.onChord(chord);
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

  const best = result?.best;
  return (
    <div className="tab-body">
      <div className="row">
        {active ? (
          <button className="btn" onClick={stop}>
            ■ Перестать слушать
          </button>
        ) : (
          <button className="btn primary" onClick={start}>
            👂 Начать слушать
          </button>
        )}
        {active && (
          <div className="level" title="Уровень сигнала с микрофона">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className={`listen-result ${active ? '' : 'off'}`}>
        {best ? (
          <>
            <div className="listen-symbol">{best.symbol}</div>
            <div className="listen-ru">{best.nameRu}</div>
            <div className="confidence" title="Насколько программа уверена">
              <span style={{ width: `${Math.round(best.confidence * 100)}%` }} className={best.confidence > 0.6 ? 'hi' : best.confidence > 0.35 ? 'mid' : 'lo'} />
              <b>{Math.round(best.confidence * 100)}%</b>
            </div>
            {result!.alternatives.length > 0 && (
              <div className="chord-alts">
                <span className="muted-label">Или:</span>
                {result!.alternatives.map((a) => (
                  <span key={a.symbol} className="alt" title={a.nameRu}>
                    {a.symbol}
                  </span>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="hint center">{active ? 'Сыграйте аккорд — один удар по всем струнам' : 'Нажмите «Начать слушать» и сыграйте аккорд на гитаре'}</div>
        )}
      </div>

      <div className="chroma-bars" title="Какие ноты слышны">
        {chroma.map((v, i) => (
          <div key={i} className="cb">
            <span style={{ height: `${Math.round(v * 100)}%` }} />
            <small>{pcName(i)}</small>
          </div>
        ))}
      </div>

      <div className="row">
        <label className="check">
          <input type="checkbox" checked={showOnBoard} onChange={(e) => setShowOnBoard(e.target.checked)} />
          Показывать аккорд на грифе
        </label>
        <label className="slider grow">
          <span>Чувствительность к удару</span>
          <input type="range" min={0} max={1} step={0.05} value={sensitivity} onChange={(e) => setSensitivity(Number(e.target.value))} />
        </label>
      </div>

      {history.length > 0 && (
        <div className="listen-history">
          <span className="muted-label">Сыграно:</span>
          {history.map((h, i) => (
            <button key={i} className="alt" onClick={() => onChord(h)} title={h.nameRu}>
              {h.symbol}
            </button>
          ))}
          <button className="link" onClick={() => setHistory([])}>
            очистить
          </button>
        </div>
      )}
      <p className="hint">
        Лучше всего: тихая комната, микрофон в 30–50 см от гитары, аккорд целиком одним ударом. Сложные аккорды (9, 11, 13) и перегруз
        распознаются хуже — смотрите на процент уверенности и варианты «Или».
      </p>
    </div>
  );
}
