// Состояние грифа: для каждой струны — открыта ли она, заглушена ли и какие лады зажаты.

import { FRET_COUNT, STRING_COUNT } from './tunings';

export interface StringState {
  /** Открытая струна звучит (O). */
  open: boolean;
  /** Струна заглушена (X). */
  muted: boolean;
  /** Зажатые лады (1..FRET_COUNT), по возрастанию. */
  frets: number[];
}

export type Board = StringState[];

export function emptyBoard(): Board {
  return Array.from({ length: STRING_COUNT }, () => ({ open: false, muted: false, frets: [] }));
}

export function isBoardEmpty(board: Board): boolean {
  return board.every((s) => !s.open && !s.muted && s.frets.length === 0);
}

/** Поставить/снять точку на ладу. Постановка точки снимает заглушение струны. */
export function toggleFret(board: Board, string: number, fret: number): Board {
  return board.map((s, i) => {
    if (i !== string) return s;
    const has = s.frets.includes(fret);
    const frets = has ? s.frets.filter((f) => f !== fret) : [...s.frets, fret].sort((a, b) => a - b);
    return { ...s, frets, muted: has ? s.muted : false };
  });
}

/** Цикл по отметке у порожка: пусто → O (открытая) → X (заглушена) → пусто. */
export function cycleNut(board: Board, string: number): Board {
  return board.map((s, i) => {
    if (i !== string) return s;
    if (!s.open && !s.muted) return { ...s, open: true };
    if (s.open) return { open: false, muted: true, frets: [] };
    return { ...s, muted: false };
  });
}

export function setNut(board: Board, string: number, mode: 'open' | 'muted' | 'none'): Board {
  return board.map((s, i) => {
    if (i !== string) return s;
    if (mode === 'open') return { ...s, open: true, muted: false };
    if (mode === 'muted') return { open: false, muted: true, frets: [] };
    return { ...s, open: false, muted: false };
  });
}

export interface SoundingNote {
  string: number;
  fret: number;
  midi: number;
}

/**
 * Звучащие ноты грифа.
 * realistic = true — как на настоящей гитаре: на каждой струне звучит только самый высокий зажатый лад.
 */
export function soundingNotes(board: Board, tuning: number[], realistic: boolean): SoundingNote[] {
  const out: SoundingNote[] = [];
  board.forEach((s, i) => {
    if (s.muted) return;
    const positions = [...(s.open ? [0] : []), ...s.frets];
    const used = realistic && positions.length ? [Math.max(...positions)] : positions;
    for (const fret of used) out.push({ string: i, fret, midi: tuning[i] + fret });
  });
  return out.sort((a, b) => a.string - b.string || a.fret - b.fret);
}

/**
 * Раскладывает набор MIDI-нот на гриф (например, аккорд, сыгранный на MIDI-клавиатуре).
 * Ищет удобную аппликатуру: по одной ноте на струну, минимальный разброс ладов.
 * Если так разложить нельзя (нот больше 6 или не хватает диапазона) — ставит каждую ноту
 * в самую низкую доступную позицию, допуская несколько точек на струне.
 */
export function boardFromMidi(notes: number[], tuning: number[]): Board {
  const uniq = [...new Set(notes)].sort((a, b) => a - b);
  const board = emptyBoard();
  if (uniq.length === 0) return board;

  let best: { assign: number[]; cost: number } | null = null;
  if (uniq.length <= STRING_COUNT) {
    const assign: number[] = new Array(uniq.length).fill(-1);
    const usedStrings = new Set<number>();
    const search = (k: number) => {
      if (k === uniq.length) {
        const frets = assign.map((s, j) => uniq[j] - tuning[s]);
        const fretted = frets.filter((f) => f > 0);
        const span = fretted.length ? Math.max(...fretted) - Math.min(...fretted) : 0;
        if (span > 4 && fretted.length > 1) return;
        const pos = fretted.length ? Math.min(...fretted) : 0;
        const cost = span * 10 + pos;
        if (!best || cost < best.cost) best = { assign: [...assign], cost };
        return;
      }
      // Ноты отсортированы по высоте — струны назначаем по возрастанию (без перекрещиваний).
      const prev = k > 0 ? assign[k - 1] : -1;
      for (let s = prev + 1; s < STRING_COUNT; s++) {
        if (usedStrings.has(s)) continue;
        const fret = uniq[k] - tuning[s];
        if (fret < 0 || fret > FRET_COUNT) continue;
        assign[k] = s;
        usedStrings.add(s);
        search(k + 1);
        usedStrings.delete(s);
        assign[k] = -1;
      }
    };
    search(0);
  }

  if (best) {
    const { assign } = best as { assign: number[] };
    assign.forEach((s, j) => {
      const fret = uniq[j] - tuning[s];
      if (fret === 0) board[s].open = true;
      else board[s].frets.push(fret);
    });
    board.forEach((s) => {
      if (!s.open && s.frets.length === 0) s.muted = true;
    });
    return board;
  }

  for (const note of uniq) {
    let placed = false;
    for (let s = STRING_COUNT - 1; s >= 0 && !placed; s--) {
      const fret = note - tuning[s];
      if (fret < 0 || fret > FRET_COUNT) continue;
      if (fret === 0) board[s].open = true;
      else if (!board[s].frets.includes(fret)) board[s].frets.push(fret);
      placed = true;
    }
  }
  board.forEach((s) => s.frets.sort((a, b) => a - b));
  return board;
}

/** Минимальная и максимальная ноты, доступные на грифе. */
export function guitarRange(tuning: number[]): [number, number] {
  return [Math.min(...tuning), Math.max(...tuning) + FRET_COUNT];
}
