import './metronome.css';
import { useRef } from 'react';
import { metronome } from '../../services/metronome';
import { usePick } from '../../store';
import type { ModuleDef } from '../types';
import type { RhythmSettings } from '../../store/model';

interface Props {
  rhythm: RhythmSettings;
  onRhythm: (patch: Partial<RhythmSettings>) => void;
}

const TEMPO_NAMES: [number, string][] = [
  [60, 'Ларго (очень медленно)'],
  [76, 'Адажио (медленно)'],
  [108, 'Анданте (спокойно)'],
  [120, 'Модерато (умеренно)'],
  [156, 'Аллегро (быстро)'],
  [176, 'Виваче (живо)'],
  [999, 'Престо (очень быстро)'],
];

export function MetronomePanel({ rhythm, onRhythm }: Props) {
  const { running, beat } = usePick((s) => s.metro);
  const taps = useRef<number[]>([]);
  const toggle = () => metronome.toggle();

  const tap = () => {
    const now = performance.now();
    taps.current = [...taps.current.filter((t) => now - t < 3000), now].slice(-6);
    if (taps.current.length >= 2) {
      const intervals = taps.current.slice(1).map((t, i) => t - taps.current[i]);
      const avg = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      onRhythm({ bpm: Math.max(40, Math.min(240, Math.round(60000 / avg))) });
    }
  };

  const tempoName = TEMPO_NAMES.find(([max]) => rhythm.bpm < max)?.[1] ?? '';

  return (
    <div className="tab-body">
      <div className="metro-display">
        <div className="metro-bpm">
          <button className="btn round" onClick={() => onRhythm({ bpm: Math.max(40, rhythm.bpm - 1) })}>
            −
          </button>
          <div>
            <b>{rhythm.bpm}</b>
            <span>ударов в минуту</span>
          </div>
          <button className="btn round" onClick={() => onRhythm({ bpm: Math.min(240, rhythm.bpm + 1) })}>
            ＋
          </button>
        </div>
        <div className="hint center">{tempoName}</div>
        <div className="metro-beats">
          {Array.from({ length: rhythm.meter }, (_, i) => (
            <span key={i} className={`${beat === i ? 'on' : ''} ${i === 0 && rhythm.accent ? 'accent' : ''}`} />
          ))}
        </div>
      </div>
      <input type="range" min={40} max={240} value={rhythm.bpm} onChange={(e) => onRhythm({ bpm: Number(e.target.value) })} />
      <div className="row">
        <label className="field inline">
          <span>Размер</span>
          <select value={rhythm.meter} onChange={(e) => onRhythm({ meter: Number(e.target.value) })}>
            {[2, 3, 4, 5, 6, 7].map((m) => (
              <option key={m} value={m}>
                {m}/4
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={rhythm.accent} onChange={(e) => onRhythm({ accent: e.target.checked })} />
          Акцент на первую долю
        </label>
      </div>
      <div className="row">
        <button className="btn primary" onClick={toggle}>
          {running ? '■ Стоп' : '▶ Старт'}
        </button>
        <button className="btn" onClick={tap} title="Постучите в нужном темпе несколько раз">
          👆 Задать темп касанием
        </button>
      </div>
    </div>
  );
}

function MetronomeView() {
  const { rhythm, patch } = usePick((s) => ({ rhythm: s.settings.rhythm, patch: s.patchRhythm }));
  return <MetronomePanel rhythm={rhythm} onRhythm={patch} />;
}

export const metronomeModule: ModuleDef = {
  id: 'metronome',
  title: 'Метроном',
  icon: '⏱',
  group: 'practice',
  description: 'Метроном 40–240 ударов в минуту с акцентом и заданием темпа касанием',
  keywords: ['темп', 'bpm', 'ритм', 'клик'],
  View: MetronomeView,
};
