import '../../ui/practice.css';
import { useEffect, useRef, useState } from 'react';
import { beatError, timingSummary, timingVerdict } from '../../core/practice/timing';
import { bus } from '../../services/bus';
import { metronome } from '../../services/metronome';
import { mic, OnsetDetector, rmsOf } from '../../services/mic';
import { store, usePick } from '../../store';
import type { ModuleDef } from '../types';

const RANGE_MS = 120;

/**
 * Тренировка ритма: метроном щёлкает, вы играете в долю (или восьмыми), микрофон ловит каждый удар
 * и показывает, насколько вы раньше или позже щелчка.
 */
function RhythmView() {
  const { rhythm, patchRhythm, best, running } = usePick((s) => ({
    rhythm: s.settings.rhythm,
    patchRhythm: s.patchRhythm,
    best: s.practice.rhythmBest,
    running: s.metro.running,
  }));
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [sub, setSub] = useState(1);
  const [latency, setLatency] = useState(40);
  const [errors, setErrors] = useState<number[]>([]);
  const beats = useRef<number[]>([]);
  const raf = useRef<number | null>(null);
  const opts = useRef({ sub, latency });
  opts.current = { sub, latency };

  useEffect(() => bus.on('metronome:beat', (b) => (beats.current = [...beats.current, b.time].slice(-16))), []);
  useEffect(() => () => stop(), []);

  const start = async () => {
    setError('');
    try {
      await mic.acquire();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setErrors([]);
    if (!metronome.running) metronome.start();
    setActive(true);
    const onsets = new OnsetDetector(0.6, 0.1);
    const buf = new Float32Array(1024);
    const tick = () => {
      if (!mic.read(buf)) return;
      const now = mic.now;
      if (onsets.feed(rmsOf(buf, 512), now)) {
        const t = now - opts.current.latency / 1000;
        const err = beatError(t, beats.current, metronome.beatDuration, opts.current.sub);
        if (err != null) setErrors((list) => [...list, err].slice(-64));
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  const stop = () => {
    if (raf.current == null) return;
    cancelAnimationFrame(raf.current);
    raf.current = null;
    mic.release();
    metronome.stop();
    setActive(false);
    setErrors((list) => {
      const s = timingSummary(list);
      if (s && s.count >= 8 && store.getState().setRhythmBest(s.accuracy))
        store.getState().toast(`Новый рекорд точности: ±${s.accuracy} мс`);
      return list;
    });
  };

  const summary = timingSummary(errors.slice(-24));
  const pos = (e: number) => `${50 + (Math.max(-RANGE_MS, Math.min(RANGE_MS, e * 1000)) / RANGE_MS) * 50}%`;

  return (
    <div className="tab-body">
      <p className="hint">Играйте по струнам точно в щелчок метронома. Точки левее середины — вы спешите, правее — отстаёте.</p>
      <div className="pr-row">
        {active ? (
          <button className="btn" onClick={stop}>
            ■ Стоп
          </button>
        ) : (
          <button className="btn primary" onClick={() => void start()}>
            ▶ Начать
          </button>
        )}
        <label className="field inline">
          <span>Темп</span>
          <input type="range" min={40} max={200} value={rhythm.bpm} onChange={(e) => patchRhythm({ bpm: Number(e.target.value) })} />
          <b>{rhythm.bpm}</b>
        </label>
        <div className="segmented" role="radiogroup" aria-label="Сетка">
          <button className={sub === 1 ? 'on' : ''} onClick={() => setSub(1)}>
            Четверти
          </button>
          <button className={sub === 2 ? 'on' : ''} onClick={() => setSub(2)}>
            Восьмые
          </button>
        </div>
        <label className="field inline" title="Звук с микрофона приходит с небольшой задержкой — она вычитается">
          <span>Задержка микрофона</span>
          <input type="range" min={0} max={150} step={5} value={latency} onChange={(e) => setLatency(Number(e.target.value))} />
          <b>{latency} мс</b>
        </label>
        {running && !active && <span className="hint">метроном играет</span>}
      </div>
      {error && <p className="error">{error}</p>}

      <div className="pr-meter" title="Последние удары относительно щелчка">
        {errors.slice(-16).map((e, i, arr) => (
          <span key={errors.length - arr.length + i} className={i < arr.length - 4 ? 'old' : ''} style={{ left: pos(e) }} />
        ))}
        <span className="lbl" style={{ left: 4 }}>
          спешите −{RANGE_MS} мс
        </span>
        <span className="lbl" style={{ right: 4 }}>
          отстаёте +{RANGE_MS} мс
        </span>
      </div>

      <div className="pr-cards" style={{ marginTop: 18 }}>
        <div className="pr-card">
          <small>Точность</small>
          <span className="pr-big">{summary ? `±${summary.accuracy}` : '—'}</span>
          <small>мс, последние удары</small>
        </div>
        <div className="pr-card">
          <small>Ударов</small>
          <b>{errors.length}</b>
        </div>
        <div className="pr-card">
          <small>Рекорд</small>
          <b>{best != null ? `±${best} мс` : '—'}</b>
        </div>
      </div>
      {summary && <p className="hint">Итог: {timingVerdict(summary)}.</p>}
    </div>
  );
}

export const rhythmModule: ModuleDef = {
  id: 'rhythm',
  title: 'Ритм',
  icon: '🥁',
  group: 'practice',
  description: 'Игра с метрономом: насколько вы спешите или отстаёте — по микрофону',
  keywords: ['метроном', 'доля', 'спешу', 'отстаю', 'бой'],
  View: RhythmView,
  isNew: true,
};
