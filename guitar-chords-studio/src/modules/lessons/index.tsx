import '../../ui/practice.css';
import './lessons.css';
import { useEffect, useRef, useState } from 'react';
import { audio } from '../../core/audio/engine';
import { boardFromFrets } from '../../core/music/fretboard';
import { matchesChord } from '../../core/practice/chordMatch';
import { voicingOptions } from '../../core/songbook/voicingPlan';
import { bus } from '../../services/bus';
import { chordListener } from '../../services/chordListener';
import { metronome } from '../../services/metronome';
import { sequencer } from '../../services/sequencer';
import { store, useGuitar, usePick } from '../../store';
import { ChordDiagram } from '../../ui/ChordDiagram';
import type { ModuleDef } from '../types';
import { LESSONS, type Lesson, type LessonStep } from './lessons';

const st = () => store.getState();

/** Поставить аккорд на гриф (без звука) и вернуть его аппликатуру. */
function showShape(chord: string) {
  const g = st().guitar();
  const frets = voicingOptions(chord, g.strings, g.capo, 1)[0]?.frets;
  if (frets) st().setBoard(boardFromFrets(frets, g.capo));
  return frets;
}

function playExample(chord: string, patternId: string, bpm: number) {
  const g = st().guitar();
  const frets = voicingOptions(chord, g.strings, g.capo, 1)[0]?.frets;
  if (!frets) return;
  st().patchRhythm({ patternId, bpm, loop: false });
  sequencer.play(st().itemsFromFrets([{ symbol: chord, frets, beats: 8 }]));
}

function StepView({ step, onDone }: { step: LessonStep; onDone: () => void }) {
  const g = useGuitar();
  const { listening, level } = usePick((s) => ({ listening: s.listen.active, level: s.listen.level }));
  const [progress, setProgress] = useState(0);
  const [strum, setStrum] = useState<{ phase: 'idle' | 'countin' | 'play' | 'done'; bars: number[]; ok?: boolean }>({
    phase: 'idle',
    bars: [],
  });
  const done = useRef(false);
  const target =
    step.kind === 'chord' ? step.chord : step.kind === 'change' ? step.pair[0] : step.kind === 'strum' ? step.chord : step.chord;

  // Новый шаг: аккорд на гриф, для шагов с гитарой — включить прослушивание.
  useEffect(() => {
    done.current = false;
    setProgress(0);
    setStrum({ phase: 'idle', bars: [] });
    if (target) showShape(target);
    if (step.kind === 'chord' || step.kind === 'change') {
      st().patchListen({ mode: 'strum', showOnBoard: false });
      void chordListener.start();
    }
    return () => {
      st().patchListen({ showOnBoard: true });
      if (metronome.running) metronome.stop();
    };
  }, [step]);

  const complete = () => {
    if (done.current) return;
    done.current = true;
    st().toast('Шаг пройден ✓');
    window.setTimeout(onDone, 700);
  };

  // Аккорд N раз / смены аккордов — по событиям микрофона.
  useEffect(() => {
    if (step.kind !== 'chord' && step.kind !== 'change') return;
    let expect = 0;
    let started = false;
    let count = 0;
    return bus.on('chord:heard', (c) => {
      if (step.kind === 'chord') {
        if (!matchesChord(step.chord, c)) return;
        count++;
        setProgress(count);
        if (count >= step.reps) complete();
      } else {
        if (!matchesChord(step.pair[expect], c)) return;
        if (started) count++;
        started = true;
        expect = 1 - expect;
        showShape(step.pair[expect]);
        setProgress(count);
        if (count >= step.changes) complete();
      }
    });
  }, [step]);

  // Бой в темп: такт отсчёта, потом считаем удары в каждом такте.
  const startStrum = () => {
    if (step.kind !== 'strum') return;
    st().patchRhythm({ bpm: step.bpm, meter: 4, accent: true });
    st().patchListen({ showOnBoard: false });
    void chordListener.start();
    const barStarts: number[] = [];
    const onsets: number[] = [];
    setStrum({ phase: 'countin', bars: [] });
    const offBeat = bus.on('metronome:beat', (b) => {
      if (b.beat !== 0) return;
      barStarts.push(b.time);
      if (barStarts.length === 2) setStrum((s) => ({ ...s, phase: 'play' }));
      if (barStarts.length === step.bars + 2) {
        const wait = Math.max(0, (b.time - audio.now) * 1000);
        window.setTimeout(() => {
          offBeat();
          offOnset();
          metronome.stop();
          const bars = Array.from(
            { length: step.bars },
            (_, i) => onsets.filter((t) => t >= barStarts[i + 1] && t < barStarts[i + 2]).length,
          );
          const avg = bars.reduce((a, x) => a + x, 0) / bars.length;
          const ok = avg >= step.perBar[0] && avg <= step.perBar[1];
          setStrum({ phase: 'done', bars, ok });
          if (ok) complete();
        }, wait);
      }
    });
    const offOnset = bus.on('mic:onset', (o) => onsets.push(o.time));
    metronome.start();
  };

  const frets = target
    ? voicingOptions(step.kind === 'change' ? step.pair[progress % 2] : target, g.strings, g.capo, 1)[0]?.frets
    : undefined;
  const need = step.kind === 'chord' ? step.reps : step.kind === 'change' ? step.changes : 0;

  return (
    <div className="lesson-step">
      <h3>{step.title}</h3>
      {step.kind === 'info' && <p>{step.text}</p>}
      {'tip' in step && step.tip && <p className="hint">💡 {step.tip}</p>}

      {step.kind !== 'info' && (
        <div className="pr-row">
          {step.kind === 'change' ? (
            step.pair.map((c, i) => {
              const f = voicingOptions(c, g.strings, g.capo, 1)[0]?.frets;
              return (
                <div key={c} className={`pr-target ${progress % 2 === i ? 'now' : ''}`}>
                  <span className="sym">{c}</span>
                  {f && <ChordDiagram frets={f} capo={g.capo} size={70} />}
                </div>
              );
            })
          ) : (
            <div className="pr-target now">
              <span className="sym">{target}</span>
              {frets && <ChordDiagram frets={frets} capo={g.capo} size={70} />}
            </div>
          )}
          {need > 0 && (
            <div className="pr-card">
              <small>{step.kind === 'chord' ? 'Сыграно' : 'Смен'}</small>
              <span className="pr-big">
                {progress}/{need}
              </span>
            </div>
          )}
          {listening && (
            <div className="level" title="Уровень микрофона">
              <span style={{ width: `${level * 100}%` }} />
            </div>
          )}
        </div>
      )}

      {step.kind === 'strum' && (
        <div className="pr-row">
          <button className="btn" onClick={() => playExample(step.chord, step.patternId, step.bpm)}>
            🔊 Послушать пример
          </button>
          <button className="btn primary" disabled={strum.phase === 'countin' || strum.phase === 'play'} onClick={startStrum}>
            ▶ Играть с метрономом ({step.bpm} уд/мин)
          </button>
          <span className="hint">
            {strum.phase === 'countin'
              ? 'Такт отсчёта: раз, два, три, четыре…'
              : strum.phase === 'play'
                ? `Играйте! ${step.bars} такта`
                : strum.phase === 'done'
                  ? `Ударов по тактам: ${strum.bars.join(', ')} — ${strum.ok ? 'отлично!' : `нужно ${step.perBar[0]}–${step.perBar[1]} в такте, попробуйте ещё раз`}`
                  : ''}
          </span>
        </div>
      )}

      <div className="pr-row">
        {step.kind === 'info' && step.chord && (
          <button className="btn" onClick={() => playExample(step.chord!, 'six', 70)}>
            🔊 Послушать пример
          </button>
        )}
        {target && step.kind !== 'strum' && (
          <button className="btn" onClick={() => (showShape(target), st().play())}>
            🔈 Как звучит
          </button>
        )}
        <span className="grow" />
        <button className={`btn ${step.kind === 'info' ? 'primary' : ''}`} onClick={onDone}>
          {step.kind === 'info' ? 'Далее →' : 'Пропустить →'}
        </button>
      </div>
    </div>
  );
}

function LessonRunner({ lesson, onBack }: { lesson: Lesson; onBack: () => void }) {
  const { progress, setLesson } = usePick((s) => ({ progress: s.practice.lessons[lesson.id], setLesson: s.setLesson }));
  const stepIndex = Math.min(progress?.step ?? 0, lesson.steps.length - 1);
  const go = (i: number) => {
    const doneAll = i >= lesson.steps.length;
    setLesson(lesson.id, { step: Math.min(i, lesson.steps.length - 1), done: doneAll || Boolean(progress?.done) });
    if (doneAll) {
      st().toast(`Урок «${lesson.title}» пройден!`);
      chordListener.stop();
      onBack();
    }
  };
  return (
    <div className="tab-body">
      <div className="pr-row">
        <button className="btn small" onClick={() => (chordListener.stop(), onBack())}>
          ← Все уроки
        </button>
        <b>
          {lesson.icon} {lesson.title}
        </b>
        <span className="hint">
          шаг {stepIndex + 1} из {lesson.steps.length}
        </span>
      </div>
      <div className="pr-steps">
        {lesson.steps.map((s, i) => (
          <span key={i} className={i < stepIndex ? 'done' : i === stepIndex ? 'now' : ''} title={s.title} onClick={() => go(i)} />
        ))}
      </div>
      <StepView key={`${lesson.id}-${stepIndex}`} step={lesson.steps[stepIndex]} onDone={() => go(stepIndex + 1)} />
    </div>
  );
}

function LessonsView() {
  const progress = usePick((s) => s.practice.lessons);
  const [open, setOpen] = useState<string | null>(null);
  const lesson = LESSONS.find((l) => l.id === open);
  if (lesson) return <LessonRunner lesson={lesson} onBack={() => setOpen(null)} />;
  return (
    <div className="tab-body">
      <p className="hint">Уроки проверяют игру через микрофон: сыграли аккорд чисто — шаг засчитан.</p>
      <div className="lesson-list">
        {LESSONS.map((l) => {
          const p = progress[l.id];
          const share = p ? (p.done ? 1 : p.step / l.steps.length) : 0;
          return (
            <button key={l.id} className="lesson-card" onClick={() => setOpen(l.id)}>
              <span className="lesson-icon">{l.icon}</span>
              <b>{l.title}</b>
              <small>{l.description}</small>
              <div className="pr-bar">
                <span style={{ width: `${Math.round(share * 100)}%` }} />
              </div>
              <small>
                {p?.done ? '✓ пройден — можно повторить' : p ? `шаг ${p.step + 1} из ${l.steps.length}` : `${l.steps.length} шагов`}
              </small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export const lessonsModule: ModuleDef = {
  id: 'lessons',
  title: 'Уроки',
  icon: '🎓',
  group: 'practice',
  description: 'Пошаговые уроки с проверкой по микрофону: первые аккорды, баррэ, бой',
  keywords: ['учиться', 'курс', 'начинающим', 'баррэ', 'шестёрка'],
  View: LessonsView,
  isNew: true,
};
