import '../../ui/practice.css';
import { useEffect, useRef, useState } from 'react';
import { matchesChord } from '../../core/practice/chordMatch';
import { voicingOptions } from '../../core/songbook/voicingPlan';
import { bus } from '../../services/bus';
import { chordListener } from '../../services/chordListener';
import { store, useGuitar, usePick } from '../../store';
import { ChordDiagram } from '../../ui/ChordDiagram';
import type { ModuleDef } from '../types';

const PAIRS: [string, string][] = [
  ['C', 'G'],
  ['Am', 'F'],
  ['G', 'D'],
  ['Em', 'C'],
  ['D', 'A'],
  ['Am', 'E'],
  ['C', 'F'],
  ['G', 'Em'],
  ['Dm', 'G'],
  ['F', 'Bm'],
];

/**
 * «Смены аккордов» (упражнение «одна минута»): программа называет пару аккордов, вы переходите
 * между ними, а микрофон считает чистые смены. Рекорд для каждой пары сохраняется.
 */
function ChangesView() {
  const g = useGuitar();
  const { best, listening, level, setChangesBest, patchListen } = usePick((s) => ({
    best: s.practice.changesBest,
    listening: s.listen.active,
    level: s.listen.level,
    setChangesBest: s.setChangesBest,
    patchListen: s.patchListen,
  }));
  const [pair, setPair] = useState<[string, string]>(PAIRS[0]);
  const [duration, setDuration] = useState(60);
  const [running, setRunning] = useState(false);
  const [left, setLeft] = useState(duration);
  const [count, setCount] = useState(0);
  const [expect, setExpect] = useState(0);
  const [result, setResult] = useState<number | null>(null);
  const state = useRef({ running: false, expect: 0, started: false, count: 0, startedAt: 0 });
  const key = pair.join('→');

  useEffect(
    () =>
      bus.on('chord:heard', (c) => {
        const st = state.current;
        if (!st.running) return;
        if (!matchesChord(pair[st.expect], c)) return;
        // Первый аккорд только открывает упражнение, каждая следующая смена — очко.
        if (st.started) st.count++;
        st.started = true;
        st.expect = 1 - st.expect;
        setCount(st.count);
        setExpect(st.expect);
      }),
    [pair],
  );

  useEffect(() => {
    if (!running) return;
    const end = performance.now() + duration * 1000;
    const id = window.setInterval(() => {
      const rest = Math.max(0, Math.ceil((end - performance.now()) / 1000));
      setLeft(rest);
      if (rest === 0) finish();
    }, 200);
    return () => window.clearInterval(id);
  }, [running]);

  const start = () => {
    patchListen({ mode: 'strum' });
    void chordListener.start();
    state.current = { running: true, expect: 0, started: false, count: 0, startedAt: performance.now() };
    setCount(0);
    setExpect(0);
    setLeft(duration);
    setResult(null);
    setRunning(true);
  };

  const finish = () => {
    state.current.running = false;
    setRunning(false);
    // При досрочной остановке — по реально прошедшему времени.
    const elapsed = Math.min(duration, Math.max(5, (performance.now() - state.current.startedAt) / 1000));
    const perMinute = Math.round((state.current.count * 60) / elapsed);
    setResult(perMinute);
    if (setChangesBest(key, perMinute)) store.getState().toast(`Новый рекорд для ${pair[0]} → ${pair[1]}: ${perMinute} смен в минуту!`);
  };

  const shape = (c: string) => voicingOptions(c, g.strings, g.capo, 1)[0]?.frets;

  return (
    <div className="tab-body">
      <p className="hint">
        Переходите между двумя аккордами как можно чаще и чище. Программа слушает гитару и считает смены — по одному удару на аккорд.
      </p>
      <div className="pr-chips">
        {PAIRS.map((p) => (
          <button key={p.join()} className={p.join() === pair.join() ? 'on' : ''} disabled={running} onClick={() => setPair(p)}>
            {p[0]} ⇄ {p[1]}
            {best[p.join('→')] ? ` · ${best[p.join('→')]}` : ''}
          </button>
        ))}
      </div>
      <div className="pr-row">
        {pair.map((c, i) => {
          const f = shape(c);
          return (
            <div key={c} className={`pr-target ${running && expect === i ? 'now' : ''}`}>
              <span className="sym">{c}</span>
              {f && <ChordDiagram frets={f} capo={g.capo} size={70} />}
            </div>
          );
        })}
      </div>
      <div className="pr-row">
        {running ? (
          <button className="btn" onClick={finish}>
            ■ Закончить
          </button>
        ) : (
          <button className="btn primary" onClick={start}>
            ▶ Старт на {duration} с
          </button>
        )}
        <label className="field inline">
          <span>Время</span>
          <select value={duration} disabled={running} onChange={(e) => setDuration(Number(e.target.value))}>
            <option value={30}>30 секунд</option>
            <option value={60}>1 минута</option>
            <option value={120}>2 минуты</option>
          </select>
        </label>
        {listening && (
          <div className="level" title="Уровень микрофона">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      <div className="pr-cards">
        <div className="pr-card">
          <small>Смен</small>
          <span className="pr-big">{count}</span>
        </div>
        <div className="pr-card">
          <small>Осталось</small>
          <b>{running ? `${left} с` : '—'}</b>
          <small>{running ? `Играйте ${pair[expect]}` : 'Нажмите «Старт» и сыграйте первый аккорд'}</small>
        </div>
        <div className="pr-card">
          <small>Рекорд для пары</small>
          <b>{best[key] ?? '—'}</b>
          <small>смен в минуту</small>
        </div>
        {result != null && (
          <div className="pr-card">
            <small>Результат</small>
            <b>{result}</b>
            <small>смен в минуту</small>
          </div>
        )}
      </div>
    </div>
  );
}

export const changesModule: ModuleDef = {
  id: 'changes',
  title: 'Смены аккордов',
  icon: '🔁',
  group: 'practice',
  description: 'Сколько чистых смен двух аккордов вы успеете за минуту — считает микрофон',
  keywords: ['смена', 'переход', 'минута', 'скорость', 'рекорд'],
  View: ChangesView,
  isNew: true,
};
