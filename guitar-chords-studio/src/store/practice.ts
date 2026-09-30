// Практика: время занятий по дням, сыгранные и выученные аккорды, прогресс уроков, рекорды.

import { EMPTY_PRACTICE, todayKey, type Practice } from './model';
import type { Slice } from './types';

/** Сколько раз аккорд нужно чисто сыграть на гитаре, чтобы он считался выученным. */
export const LEARN_THRESHOLD = 5;

export interface PracticeSlice {
  practice: Practice;
  addPracticeSeconds: (sec: number) => void;
  /** Аккорд сыгран на гитаре (распознан микрофоном). */
  notePlayedChord: (symbol: string) => void;
  setLesson: (id: string, p: { step: number; done: boolean }) => void;
  setChangesBest: (pair: string, perMinute: number) => boolean;
  setRhythmBest: (errMs: number) => boolean;
  resetPractice: () => void;
}

export const createPracticeSlice: Slice<PracticeSlice> = (set, get) => {
  const patch = (fn: (p: Practice) => Practice) => set((s) => ({ practice: fn(s.practice) }));
  return {
    practice: EMPTY_PRACTICE,
    addPracticeSeconds: (sec) =>
      patch((p) => {
        const k = todayKey();
        const day = p.days[k] ?? { seconds: 0, chords: [] };
        return { ...p, days: { ...p.days, [k]: { ...day, seconds: day.seconds + sec } } };
      }),
    notePlayedChord: (symbol) =>
      patch((p) => {
        const k = todayKey();
        const day = p.days[k] ?? { seconds: 0, chords: [] };
        const count = (p.heardCount[symbol] ?? 0) + 1;
        const learned = count >= LEARN_THRESHOLD && !p.learned.includes(symbol) ? [...p.learned, symbol] : p.learned;
        return {
          ...p,
          heardCount: { ...p.heardCount, [symbol]: count },
          learned,
          days: { ...p.days, [k]: { ...day, chords: day.chords.includes(symbol) ? day.chords : [...day.chords, symbol] } },
        };
      }),
    setLesson: (id, v) => patch((p) => ({ ...p, lessons: { ...p.lessons, [id]: v } })),
    setChangesBest: (pair, perMinute) => {
      const best = get().practice.changesBest[pair] ?? 0;
      if (perMinute <= best) return false;
      patch((p) => ({ ...p, changesBest: { ...p.changesBest, [pair]: perMinute } }));
      return true;
    },
    setRhythmBest: (errMs) => {
      const best = get().practice.rhythmBest;
      if (best != null && errMs >= best) return false;
      patch((p) => ({ ...p, rhythmBest: errMs }));
      return true;
    },
    resetPractice: () => set({ practice: EMPTY_PRACTICE }),
  };
};
