import { useEffect, useRef, useState } from 'react';
import { audio } from '../audio/engine';
import { detectChord, type DetectionResult } from '../music/chords';
import { chromaFromSpectrum, detectPitch, freqToMidi, pickPitchClasses } from '../music/pitch';
import { midiName, mod12, pcName, pcNameRu } from '../music/notes';

interface Props {
  tuning: number[];
  capo: number;
  onChordToBoard: (midis: number[]) => void;
}

interface Reading {
  freq: number;
  midi: number;
  cents: number;
}

export function TunerPanel({ tuning, capo, onChordToBoard }: Props) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [reading, setReading] = useState<Reading | null>(null);
  const [level, setLevel] = useState(0);
  const [listening, setListening] = useState(false);
  const [chord, setChord] = useState<{ result: DetectionResult; midis: number[] } | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const history = useRef<number[]>([]);
  const chromaAcc = useRef<{ chroma: number[]; bass: number[]; until: number } | null>(null);

  const stop = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    analyserRef.current = null;
    setActive(false);
    setReading(null);
    setLevel(0);
  };

  useEffect(() => stop, []);

  const start = async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      streamRef.current = stream;
      const ctx = audio.context;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 8192;
      analyser.smoothingTimeConstant = 0.3;
      src.connect(analyser);
      analyserRef.current = analyser;
      setActive(true);
      const time = new Float32Array(analyser.fftSize);
      const freq = new Float32Array(analyser.frequencyBinCount);

      const loop = () => {
        const an = analyserRef.current;
        if (!an) return;
        an.getFloatTimeDomainData(time);
        let rms = 0;
        for (let i = 0; i < time.length; i++) rms += time[i] * time[i];
        setLevel(Math.min(1, Math.sqrt(rms / time.length) * 8));

        const r = detectPitch(time.subarray(0, 4096), ctx.sampleRate);
        if (r && r.clarity > 0.8) {
          history.current = [...history.current, r.freq].slice(-5);
          const sorted = [...history.current].sort((a, b) => a - b);
          const f = sorted[Math.floor(sorted.length / 2)];
          const m = freqToMidi(f);
          const midi = Math.round(m);
          setReading({ freq: f, midi, cents: Math.round((m - midi) * 100) });
        }

        const acc = chromaAcc.current;
        if (acc) {
          an.getFloatFrequencyData(freq);
          chromaFromSpectrum(freq, ctx.sampleRate, an.fftSize).forEach((v, i) => (acc.chroma[i] += v));
          const low = detectPitch(time.subarray(0, 4096), ctx.sampleRate, 60, 400);
          if (low && low.clarity > 0.6) acc.bass.push(Math.round(freqToMidi(low.freq)));
          if (performance.now() > acc.until) {
            chromaAcc.current = null;
            finishChord(acc.chroma, acc.bass);
          }
        }
        rafRef.current = requestAnimationFrame(loop);
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

  const finishChord = (chroma: number[], bass: number[]) => {
    setListening(false);
    const pcs = pickPitchClasses(chroma, 0.3, 5);
    if (pcs.length === 0) {
      setChord(null);
      setError('Не расслышал аккорд — сыграйте громче и ближе к микрофону.');
      return;
    }
    // Бас — самая частая низкая нота, если она входит в найденные.
    const counts = new Map<number, number>();
    for (const b of bass) counts.set(b, (counts.get(b) ?? 0) + 1);
    const bassMidi = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    const bassPc = bassMidi != null && pcs.includes(mod12(bassMidi)) ? mod12(bassMidi) : pcs[0];
    const midis = [48 + bassPc, ...pcs.filter((pc) => pc !== bassPc).map((pc) => 60 + pc)];
    setChord({ result: detectChord(midis), midis });
  };

  const listenChord = () => {
    setError('');
    setChord(null);
    setListening(true);
    chromaAcc.current = { chroma: new Array(12).fill(0), bass: [], until: performance.now() + 1500 };
  };

  // Ближайшая струна текущего строя.
  const target = reading
    ? tuning
        .map((open, s) => ({ s, midi: open + capo, diff: freqToMidi(reading.freq) - (open + capo) }))
        .sort((a, b) => Math.abs(a.diff) - Math.abs(b.diff))[0]
    : null;
  const targetCents = target ? Math.round(target.diff * 100) : 0;
  const inTune = reading && Math.abs(reading.cents) <= 5;
  const angle = reading ? Math.max(-50, Math.min(50, reading.cents)) * 1.6 : 0;

  return (
    <div className="tab-body">
      <div className="row">
        {active ? (
          <button className="btn" onClick={stop}>
            ■ Выключить микрофон
          </button>
        ) : (
          <button className="btn primary" onClick={start}>
            🎤 Включить тюнер
          </button>
        )}
        {active && (
          <div className="level" title="Уровень сигнала">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className={`tuner ${active ? '' : 'off'}`}>
        <svg viewBox="0 0 240 130" className="tuner-gauge">
          <path d="M 20 120 A 100 100 0 0 1 220 120" className="arc" />
          {[-50, -25, 0, 25, 50].map((c) => {
            const a = ((c * 1.6 - 90) * Math.PI) / 180;
            return (
              <g key={c}>
                <line x1={120 + 88 * Math.cos(a)} y1={120 + 88 * Math.sin(a)} x2={120 + 100 * Math.cos(a)} y2={120 + 100 * Math.sin(a)} className="tick" />
                <text x={120 + 76 * Math.cos(a)} y={120 + 76 * Math.sin(a)} className="tick-label">
                  {c > 0 ? `+${c}` : c}
                </text>
              </g>
            );
          })}
          <line x1="120" y1="120" x2="120" y2="30" className={`needle ${inTune ? 'ok' : ''}`} transform={`rotate(${angle} 120 120)`} />
          <circle cx="120" cy="120" r="6" className="hub" />
        </svg>
        <div className={`tuner-note ${inTune ? 'ok' : ''}`}>
          {reading ? (
            <>
              <b>{pcName(reading.midi)}</b>
              <sub>{Math.floor(reading.midi / 12) - 1}</sub>
            </>
          ) : (
            '—'
          )}
        </div>
        <div className="tuner-info">
          {reading ? (
            <>
              {pcNameRu(reading.midi)} · {reading.freq.toFixed(1)} Гц · {reading.cents > 0 ? '+' : ''}
              {reading.cents} центов
            </>
          ) : active ? (
            'Сыграйте одну открытую струну'
          ) : (
            'Включите тюнер и разрешите доступ к микрофону'
          )}
        </div>
        {target && reading && (
          <div className={`tuner-hint ${Math.abs(targetCents) <= 5 ? 'ok' : ''}`}>
            {tuning.length - target.s}-я струна ({midiName(target.midi)}):{' '}
            {Math.abs(targetCents) <= 5
              ? 'настроена ✓'
              : targetCents < 0
                ? `ниже на ${-targetCents} ц — подтяните`
                : `выше на ${targetCents} ц — ослабьте`}
          </div>
        )}
      </div>

      <div className="row">
        <span className="hint">Эталон:</span>
        {tuning.map((open, s) => (
          <button key={s} className="btn small" onClick={() => audio.playNote(open + capo, 0.9)} title={`Сыграть ${midiName(open + capo)}`}>
            {pcName(open + capo)}
          </button>
        ))}
      </div>

      <div className="subpanel">
        <div className="row between">
          <b>Аккорд по звуку</b>
          <span className="badge">эксперимент</span>
        </div>
        <p className="hint">Сыграйте аккорд и держите его звучание около 1,5 секунды. Точность зависит от микрофона и шума.</p>
        <button className="btn" onClick={listenChord} disabled={!active || listening}>
          {listening ? 'Слушаю…' : '👂 Распознать аккорд'}
        </button>
        {chord && (
          <div className="row">
            <span className="big-sym">{chord.result.primary?.symbol ?? chord.result.noteNames.join(' ')}</span>
            <span>{chord.result.primary?.nameRu ?? 'Неизвестный аккорд'}</span>
            <button className="btn small" onClick={() => onChordToBoard(chord.midis)}>
              ⇩ На гриф
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
