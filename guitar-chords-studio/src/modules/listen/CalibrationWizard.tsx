import { useEffect, useRef, useState } from 'react';
import { buildCalibration, measureOpenString, type Calibration } from '../../core/analysis/calibration';
import { SpectrumAnalyzer } from '../../core/analysis/dsp';
import { midiName, pcNameRu } from '../../core/music/notes';
import { chordListener } from '../../services/chordListener';
import { MIC_FRAME, OnsetDetector, mic, rmsOf } from '../../services/mic';
import { store, useGuitar } from '../../store';

type Measure = ReturnType<typeof measureOpenString>;

/**
 * Калибровка: открытые струны по очереди, от басовой к тонкой. По каждой — строй и как микрофон
 * передаёт её основной тон. В конце — таблица и сохранение.
 */
export function CalibrationWizard({ onClose }: { onClose: () => void }) {
  const g = useGuitar();
  const opens = g.strings.map((m) => m + g.capo);
  const n = opens.length;
  const [step, setStep] = useState(0);
  const [results, setResults] = useState<(Measure | null)[]>(() => new Array(n).fill(null));
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [level, setLevel] = useState(0);
  const stepRef = useRef(step);
  stepRef.current = step;
  const done = step >= n;

  useEffect(() => {
    let raf = 0;
    let alive = true;
    const wasListening = chordListener.active;
    if (wasListening) chordListener.stop();
    const buf = new Float32Array(MIC_FRAME);
    const analyzer = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate);
    const onsets = new OnsetDetector(0.55);
    let measureAt = -1;
    void mic
      .acquire()
      .then(() => {
        if (!alive) return mic.release();
        const tick = () => {
          if (!mic.read(buf)) return;
          const now = mic.now;
          const rms = rmsOf(buf);
          setLevel(Math.min(1, rms * 6));
          if (onsets.feed(rms, now) && stepRef.current < n) {
            measureAt = now + 0.4;
            setMsg('Слушаю…');
          }
          if (measureAt > 0 && now >= measureAt) {
            measureAt = -1;
            const s = stepRef.current;
            const gain = mic.gain || 1;
            const { semi } = analyzer.semitones(buf, 0);
            for (let i = 0; i < semi.length; i++) semi[i] /= gain;
            const m = measureOpenString(buf.subarray(MIC_FRAME - 8192), mic.sampleRate, semi, opens[s]);
            setResults((r) => r.map((x, i) => (i === s ? m : x)));
            if (m.cents == null) {
              setMsg(
                m.heardMidi != null
                  ? `Слышу ${midiName(m.heardMidi)}, а ждал ${midiName(opens[s])}. Сыграйте открытую струну ещё раз или нажмите «Дальше».`
                  : 'Не расслышал ноту — сыграйте струну погромче или поднесите гитару к микрофону.',
              );
            } else {
              setMsg(`Готово: ${midiName(opens[s])}, строй ${m.cents > 0 ? '+' : ''}${m.cents} ц`);
              window.setTimeout(() => alive && setStep((x) => (x === s ? x + 1 : x)), 700);
            }
          }
          raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      mic.release();
    };
  }, []);

  const measured = results.filter((r): r is Measure => r != null);
  const cal: Calibration | null = done && measured.length ? buildCalibration(measured) : null;
  const save = () => {
    if (!cal) return;
    store.getState().patchListen({ calibration: cal });
    store.getState().toast('Калибровка сохранена');
    onClose();
  };

  return (
    <div className="calib">
      <div className="calib-head">
        <b>🎯 Калибровка под гитару и микрофон</b>
        <button className="btn small" onClick={onClose}>
          ✕
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {!done ? (
        <>
          <p>
            Сыграйте <b>открытую {n - step}-ю струну</b> ({midiName(opens[step])} · {pcNameRu(opens[step] % 12).toLowerCase()}) и дайте ей
            прозвучать. Остальные струны придержите ладонью.
            {g.capo > 0 && ` С каподастром на ${g.capo}-м ладу.`}
          </p>
          <div className="level" title="Уровень микрофона">
            <span style={{ width: `${level * 100}%` }} />
          </div>
          {msg && <p className="hint">{msg}</p>}
          <div className="calib-steps">
            {opens.map((m, i) => (
              <span key={i} className={i < step ? 'done' : i === step ? 'now' : ''}>
                {n - i}: {midiName(m)}
              </span>
            ))}
          </div>
          <div className="row">
            <button className="btn" onClick={() => setStep((s) => s + 1)}>
              Дальше →
            </button>
          </div>
        </>
      ) : cal ? (
        <>
          <table className="calib-table">
            <thead>
              <tr>
                <th>Струна</th>
                <th>Строй</th>
                <th title="Насколько микрофон слышит основной тон струны">Основной тон</th>
                <th>Подъём</th>
              </tr>
            </thead>
            <tbody>
              {cal.strings.map((s) => {
                const idx = opens.indexOf(s.openMidi);
                const gIdx = s.openMidi - 24;
                const off = s.cents == null ? null : Math.abs(s.cents - cal.tuningCents);
                return (
                  <tr key={s.openMidi}>
                    <td>
                      {n - idx} · {midiName(s.openMidi)}
                    </td>
                    <td className={off == null ? 'bad' : off > 15 ? 'warn' : 'ok'}>
                      {s.cents == null ? 'не определён' : `${s.cents > 0 ? '+' : ''}${s.cents} ц`}
                      {off != null && off > 15 && ' — подстройте'}
                    </td>
                    <td className={s.fundamental < 0.3 ? 'warn' : 'ok'}>{Math.round(Math.min(1, s.fundamental) * 100)}%</td>
                    <td>×{(cal.gains[gIdx] ?? 1).toFixed(1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="hint">
            Общий строй гитары: {cal.tuningCents > 0 ? '+' : ''}
            {cal.tuningCents} ц — программа будет это учитывать. Где основной тон слышен слабо, программа поднимет эти ноты («подъём»),
            чтобы не путать их с октавой выше.
          </p>
          <div className="row">
            <button className="btn primary" onClick={save}>
              Сохранить
            </button>
            <button className="btn" onClick={() => (setStep(0), setResults(new Array(n).fill(null)), setMsg(''))}>
              Заново
            </button>
          </div>
        </>
      ) : (
        <p className="hint">Ни одна струна не записалась. Нажмите «Заново».</p>
      )}
    </div>
  );
}
