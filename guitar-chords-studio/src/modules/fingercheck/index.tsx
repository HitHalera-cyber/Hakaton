import '../../ui/practice.css';
import { useEffect, useRef, useState } from 'react';
import { alignPluck, judgeString, summarize, type ExpectedString, type StringStatus } from '../../core/analysis/fingerCheck';
import type { Pluck } from '../../core/analysis/stringPick';
import { listenPlucks } from '../../services/pluckListener';
import { midiName, pcName } from '../../core/music/notes';
import { useGuitar } from '../../store';
import type { ModuleDef } from '../types';

type Phase = 'idle' | 'listening' | 'done';

const STATUS: Record<StringStatus, { icon: string; text: string; cls: string }> = {
  ok: { icon: '✓', text: 'звучит чисто', cls: '' },
  weak: { icon: '⚠', text: 'нота верная, но с призвуком — палец касается струны или прижат далеко от лада (дребезг)', cls: 'warn' },
  quiet: { icon: '⚠', text: 'звучит тихо и коротко — струну приглушает соседний палец', cls: 'warn' },
  missing: { icon: '✗', text: 'не звучит — струну глушит палец', cls: 'bad' },
  open: { icon: '✗', text: 'звучит открытая струна — палец не прижал её', cls: 'bad' },
  wrong: { icon: '✗', text: 'звучит не та нота — палец не на том ладу или не на той струне', cls: 'bad' },
  silent: { icon: '✓', text: 'молчит, как и должна', cls: '' },
  ringing: { icon: '✗', text: 'звенит, хотя должна молчать — заглушите её пальцем или не задевайте', cls: 'bad' },
  skipped: { icon: '·', text: 'не сыграна', cls: 'muted' },
};

/**
 * Проверка аппликатуры: зажмите аккорд и проведите по струнам по одной, от басовой к тонкой.
 * Каждая струна проверяется сразу после щипка.
 */
function FingerCheckView() {
  const g = useGuitar();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [plucks, setPlucks] = useState<(Pluck | null)[]>([]);
  const [level, setLevel] = useState(0);
  const stopRef = useRef<(() => void) | null>(null);
  const cursor = useRef(0);
  const lastPluckAt = useRef(0);

  const n = g.strings.length;
  const expected: ExpectedString[] = Array.from({ length: n }, (_, s) => ({
    string: s,
    midi: g.boardNotes.find((x) => x.string === s)?.midi ?? null,
    openMidi: g.strings[s] + g.capo,
  }));
  const hasChord = expected.some((e) => e.midi != null);
  const expRef = useRef(expected);
  expRef.current = expected;

  const stop = () => {
    stopRef.current?.();
    stopRef.current = null;
  };
  useEffect(() => stop, []);
  // Пауза после последнего щипка — проверка закончена.
  useEffect(() => {
    if (phase !== 'listening') return;
    const id = window.setInterval(() => {
      if (cursor.current > 0 && Date.now() - lastPluckAt.current > 2500) finish();
    }, 300);
    return () => window.clearInterval(id);
  }, [phase]);

  const finish = () => {
    stop();
    setPhase('done');
  };

  const check = async () => {
    setError('');
    setPlucks(new Array(n).fill(null));
    cursor.current = 0;
    try {
      stopRef.current = await listenPlucks({
        lo: Math.min(...g.strings) + g.capo,
        hi: Math.max(...g.strings) + g.capo + 15,
        onLevel: setLevel,
        onPluck: (p) => {
          const exp = expRef.current;
          const s = alignPluck(exp, cursor.current, p);
          if (s >= exp.length) return;
          cursor.current = s + 1;
          lastPluckAt.current = Date.now();
          setPlucks((list) => list.map((x, i) => (i === s ? p : x)));
          if (cursor.current >= exp.length) window.setTimeout(finish, 400);
        },
      });
      setPhase('listening');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const verdicts = expected.map((e, i) => judgeString(e, plucks[i] ?? null));
  const sum = phase === 'done' ? summarize(verdicts, plucks) : null;
  const next = cursor.current;

  return (
    <div className="tab-body">
      <p className="hint">
        Поставьте аккорд на гриф (кликом, из справочника или песенника) и зажмите его на гитаре. Нажмите «Проверить» и проведите по струнам{' '}
        <b>по одной, от {n}-й к 1-й</b> — заглушённые тоже. Каждая струна проверяется сразу после щипка.
      </p>
      <div className="pr-row">
        <div className="pr-target">
          <span className="sym">{g.result.primary?.symbol ?? (hasChord ? '?' : '—')}</span>
          <small className="hint">{hasChord ? 'аккорд на грифе' : 'поставьте аккорд на гриф'}</small>
        </div>
        {phase === 'listening' ? (
          <>
            <span className="listening-note">● Щипайте струны по одной…</span>
            <div className="level" title="Уровень микрофона">
              <span style={{ width: `${level * 100}%` }} />
            </div>
            <button className="btn small" onClick={finish}>
              Готово
            </button>
          </>
        ) : (
          <button className="btn primary" disabled={!hasChord} onClick={() => void check()}>
            🎤 {phase === 'done' ? 'Проверить ещё раз' : 'Проверить'}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      {phase !== 'idle' && (
        <div className="fc-result">
          {sum && (
            <div className="pr-cards">
              <div className="pr-card">
                <small>Чисто звучат</small>
                <span className="pr-big">
                  {sum.good}/{sum.total}
                </span>
              </div>
            </div>
          )}
          <div className="fc-strings">
            {verdicts.map((v, i) => {
              const waiting = phase === 'listening' && !plucks[i];
              const st = waiting
                ? { icon: i === next ? '▶' : '·', text: i === next ? 'щипните эту струну' : '', cls: 'muted' }
                : STATUS[v.status];
              return (
                <div key={v.string} className={`fc-string ${st.cls} ${waiting && i === next ? 'next' : ''}`}>
                  <b>{n - v.string}</b>
                  <span className="fc-note">{v.midi != null ? midiName(v.midi) : `× ${pcName(expected[i].openMidi)}`}</span>
                  <span className="fc-icon">{st.icon}</span>
                  <span className="fc-text">
                    {st.text}
                    {v.heard != null && !waiting && ` (слышно ${midiName(v.heard)})`}
                  </span>
                </div>
              );
            })}
          </div>
          {sum && sum.good === sum.total && <p className="ok-text">Отлично: аккорд звучит чисто!</p>}
        </div>
      )}
    </div>
  );
}

export const fingercheckModule: ModuleDef = {
  id: 'fingercheck',
  title: 'Проверка аппликатуры',
  icon: '🩺',
  group: 'practice',
  description: 'Какая струна глушится или звенит в сыгранном аккорде',
  keywords: ['чисто', 'глушится', 'дребезг', 'баррэ', 'звенит'],
  View: FingerCheckView,
};
