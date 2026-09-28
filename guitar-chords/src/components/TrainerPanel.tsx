import { useEffect, useRef, useState } from 'react';
import { audio } from '../audio/engine';
import { CHORD_TEMPLATES, type ChordTemplate } from '../music/chords';
import { chordPitchClasses } from '../music/chordParse';
import type { Frets } from '../music/fretboard';
import { mod12, pcName, pcNameRu, spelledName, spelledRu } from '../music/notes';
import { keyRootSpelling } from '../music/scales';
import { FRET_COUNT } from '../music/tunings';
import { boardFromFrets, soundingNotes } from '../music/fretboard';
import { generateVoicings } from '../music/voicings';
import type { CellFlash } from './Fretboard';

type Mode = 'notes' | 'build' | 'ear';

interface Props {
  tuning: number[];
  capo: number;
  soundingMidis: number[];
  registerCellHandler: (fn: ((s: number, f: number) => boolean) | null) => void;
  setFlash: (f: CellFlash | null) => void;
  loadFrets: (frets: Frets, symbol: string) => void;
  clearBoard: () => void;
}

const tpl = (id: string) => CHORD_TEMPLATES.find((t) => t.id === id)!;
const EAR_LEVELS: { name: string; ids: string[] }[] = [
  { name: 'Мажор / минор', ids: ['maj', 'min'] },
  { name: '+ септаккорды', ids: ['maj', 'min', '7', 'maj7', 'm7'] },
  { name: 'Все основные', ids: ['maj', 'min', '7', 'maj7', 'm7', 'dim', 'aug', 'sus2', 'sus4'] },
];
const BUILD_LEVELS: { name: string; ids: string[] }[] = [
  { name: 'Трезвучия', ids: ['maj', 'min'] },
  { name: 'Септаккорды', ids: ['7', 'maj7', 'm7'] },
  { name: 'Всё подряд', ids: ['maj', 'min', '7', 'maj7', 'm7', 'sus4', 'sus2', 'dim', 'add9', 'm7b5'] },
];

const rand = (n: number) => Math.floor(Math.random() * n);
const chordName = (rootPc: number, t: ChordTemplate) => {
  const minor = t.degrees.includes('b3') && !t.degrees.includes('3');
  const root = keyRootSpelling(rootPc, minor ? 'minor' : 'major');
  return { symbol: spelledName(root) + t.suffix, ru: `${spelledRu(root)} ${t.ru}` };
};

export function TrainerPanel(p: Props) {
  const [mode, setMode] = useState<Mode>('notes');
  const [score, setScore] = useState({ ok: 0, total: 0, streak: 0 });
  const [feedback, setFeedback] = useState<{ text: string; ok: boolean } | null>(null);
  const [anyString, setAnyString] = useState(false);
  const [noteQ, setNoteQ] = useState<{ s: number; pc: number } | null>(null);
  const [buildLevel, setBuildLevel] = useState(0);
  const [buildQ, setBuildQ] = useState<{ rootPc: number; id: string } | null>(null);
  const [earLevel, setEarLevel] = useState(0);
  const [earQ, setEarQ] = useState<{ rootPc: number; id: string; answered: boolean } | null>(null);

  const answer = (ok: boolean, text: string) => {
    setFeedback({ ok, text });
    setScore((s) => ({ ok: s.ok + (ok ? 1 : 0), total: s.total + 1, streak: ok ? s.streak + 1 : 0 }));
  };

  // ---------- Найти ноту ----------
  const nextNote = () => {
    const s = rand(p.tuning.length);
    const f = p.capo + 1 + rand(Math.min(12, FRET_COUNT - p.capo));
    setNoteQ({ s, pc: mod12(p.tuning[s] + f) });
    setFeedback(null);
  };
  const noteRef = useRef(noteQ);
  noteRef.current = noteQ;
  const anyRef = useRef(anyString);
  anyRef.current = anyString;

  useEffect(() => {
    if (mode !== 'notes') {
      p.registerCellHandler(null);
      return;
    }
    if (!noteRef.current) nextNote();
    p.registerCellHandler((s, f) => {
      const q = noteRef.current;
      if (!q) return true;
      const midi = p.tuning[s] + f;
      audio.playNote(midi, 0.8);
      const ok = mod12(midi) === q.pc && (anyRef.current || s === q.s);
      p.setFlash({ s, f, ok });
      if (ok) {
        answer(true, `Верно! ${pcName(midi)} на ${f} ладу`);
        setTimeout(nextNote, 700);
      } else if (mod12(midi) === q.pc) {
        answer(false, `Это ${pcName(midi)}, но на другой струне — нужна ${p.tuning.length - q.s}-я`);
      } else {
        answer(false, `Это ${pcNameRu(midi)} (${pcName(midi)}), а нужна ${pcNameRu(q.pc)}`);
      }
      return true;
    });
    return () => p.registerCellHandler(null);
  }, [mode, p.tuning, p.capo]);

  // ---------- Построить аккорд ----------
  const nextBuild = () => {
    const ids = BUILD_LEVELS[buildLevel].ids;
    setBuildQ({ rootPc: rand(12), id: ids[rand(ids.length)] });
    setFeedback(null);
    p.clearBoard();
  };
  const checkBuild = () => {
    if (!buildQ) return;
    const t = tpl(buildQ.id);
    const tones = chordPitchClasses(buildQ.rootPc, t);
    const pcs = new Set(p.soundingMidis.map(mod12));
    const missing = tones.filter((x) => !x.optional && !pcs.has(x.pc)).map((x) => pcName(x.pc));
    const extra = [...pcs].filter((pc) => !tones.some((x) => x.pc === pc)).map(pcName);
    const bassOk = p.soundingMidis.length > 0 && mod12(Math.min(...p.soundingMidis)) === buildQ.rootPc;
    if (!p.soundingMidis.length) {
      setFeedback({ ok: false, text: 'Сначала поставьте точки на грифе' });
      return;
    }
    if (missing.length || extra.length) {
      answer(false, [missing.length ? `не хватает: ${missing.join(', ')}` : '', extra.length ? `лишние: ${extra.join(', ')}` : ''].filter(Boolean).join('; '));
      return;
    }
    answer(true, bassOk ? 'Верно! Все ноты на месте.' : 'Ноты верные, но в басу не тоника — получилось обращение. Засчитано!');
    audio.strum(p.soundingMidis.map((midi) => ({ midi })));
  };
  const hintBuild = () => {
    if (!buildQ) return;
    const v = generateVoicings(buildQ.rootPc, tpl(buildQ.id), p.tuning, { capo: p.capo, limit: 1 })[0];
    if (v) p.loadFrets(v.frets, chordName(buildQ.rootPc, tpl(buildQ.id)).symbol);
    setFeedback({ ok: false, text: 'Подсказка поставлена на гриф (ответ не засчитан)' });
  };

  // ---------- На слух ----------
  const playEar = (q: { rootPc: number; id: string }) => {
    const v = generateVoicings(q.rootPc, tpl(q.id), p.tuning, { capo: p.capo, limit: 3 })[0];
    const notes = v
      ? soundingNotes(boardFromFrets(v.frets, p.capo), p.tuning, p.capo).map((n) => ({ midi: n.midi, string: n.string }))
      : chordPitchClasses(q.rootPc, tpl(q.id)).map((x, i) => ({ midi: 48 + x.pc + (i ? 12 : 0) }));
    audio.stopAll(0.03);
    audio.strum(notes, 'down');
  };
  const nextEar = () => {
    const ids = EAR_LEVELS[earLevel].ids;
    const q = { rootPc: rand(12), id: ids[rand(ids.length)], answered: false };
    setEarQ(q);
    setFeedback(null);
    playEar(q);
  };
  const answerEar = (id: string) => {
    if (!earQ || earQ.answered) return;
    const t = tpl(earQ.id);
    const name = chordName(earQ.rootPc, t);
    const ok = id === earQ.id;
    answer(ok, ok ? `Верно! Это ${name.symbol} — ${name.ru}` : `Нет, это был ${t.suffix || 'мажор'} (${name.symbol} — ${name.ru})`);
    setEarQ({ ...earQ, answered: true });
  };

  const q = noteQ;
  return (
    <div className="tab-body">
      <div className="segmented wide">
        <button className={mode === 'notes' ? 'on' : ''} onClick={() => setMode('notes')}>
          Найди ноту
        </button>
        <button className={mode === 'build' ? 'on' : ''} onClick={() => setMode('build')}>
          Построй аккорд
        </button>
        <button className={mode === 'ear' ? 'on' : ''} onClick={() => setMode('ear')}>
          Угадай на слух
        </button>
      </div>

      <div className="score">
        Правильно: <b>{score.ok}</b> из <b>{score.total}</b>
        {score.total > 0 && <> ({Math.round((score.ok / score.total) * 100)}%)</>} · серия: <b>{score.streak}</b>
        <button className="link" onClick={() => setScore({ ok: 0, total: 0, streak: 0 })}>
          сбросить
        </button>
      </div>

      {mode === 'notes' && q && (
        <>
          <div className="question">
            Найдите ноту <b>{pcNameRu(q.pc)}</b> ({pcName(q.pc)}) {anyString ? 'на любой струне' : <>на <b>{p.tuning.length - q.s}-й струне</b></>}
          </div>
          <p className="hint">Кликайте по грифу — точки не ставятся, пока открыта эта вкладка.</p>
          <div className="row">
            <label className="check">
              <input type="checkbox" checked={anyString} onChange={(e) => setAnyString(e.target.checked)} />
              На любой струне
            </label>
            <button className="btn small" onClick={nextNote}>
              Другая нота
            </button>
          </div>
        </>
      )}

      {mode === 'build' && (
        <>
          <div className="row">
            <label className="field inline">
              <span>Уровень</span>
              <select value={buildLevel} onChange={(e) => setBuildLevel(Number(e.target.value))}>
                {BUILD_LEVELS.map((l, i) => (
                  <option key={i} value={i}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn" onClick={nextBuild}>
              {buildQ ? 'Следующий' : 'Начать'}
            </button>
          </div>
          {buildQ && (
            <>
              <div className="question">
                Поставьте на грифе <b>{chordName(buildQ.rootPc, tpl(buildQ.id)).symbol}</b>
                <small>{chordName(buildQ.rootPc, tpl(buildQ.id)).ru}</small>
              </div>
              <div className="row">
                <button className="btn primary" onClick={checkBuild}>
                  ✓ Проверить
                </button>
                <button className="btn" onClick={hintBuild}>
                  💡 Подсказка
                </button>
              </div>
            </>
          )}
        </>
      )}

      {mode === 'ear' && (
        <>
          <div className="row">
            <label className="field inline">
              <span>Уровень</span>
              <select value={earLevel} onChange={(e) => setEarLevel(Number(e.target.value))}>
                {EAR_LEVELS.map((l, i) => (
                  <option key={i} value={i}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn primary" onClick={nextEar}>
              {earQ ? '▶ Следующий аккорд' : '▶ Начать'}
            </button>
            {earQ && (
              <button className="btn" onClick={() => playEar(earQ)}>
                🔁 Повторить
              </button>
            )}
          </div>
          {earQ && (
            <div className="answers">
              {EAR_LEVELS[earLevel].ids.map((id) => (
                <button
                  key={id}
                  className={`btn ${earQ.answered && id === earQ.id ? 'correct' : ''}`}
                  onClick={() => answerEar(id)}
                  disabled={earQ.answered}
                >
                  {tpl(id).ru}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {feedback && <div className={`feedback ${feedback.ok ? 'ok' : 'bad'}`}>{feedback.text}</div>}
    </div>
  );
}
