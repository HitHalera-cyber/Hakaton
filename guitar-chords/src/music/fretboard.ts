// Состояние грифа: для каждой струны — открыта ли она, заглушена ли и какие лады зажаты.
// Каподастр на ладу capo: «открытая» струна звучит как лад capo, зажимать можно лады выше capo.

import { FRET_COUNT } from './tunings';

export interface StringState {
  /** Открытая струна звучит (O). */
  open: boolean;
  /** Струна заглушена (X). */
  muted: boolean;
  /** Зажатые лады (1..FRET_COUNT), по возрастанию. */
  frets: number[];
}

export type Board = StringState[];

export function emptyBoard(strings = 6): Board {
  return Array.from({ length: strings }, () => ({ open: false, muted: false, frets: [] }));
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
  /** Реальный лад (открытая струна с каподастром — лад capo). */
  fret: number;
  midi: number;
}

/** Звучащие ноты грифа: все поставленные точки и открытые струны (кроме заглушённых). */
export function soundingNotes(board: Board, tuning: number[], capo = 0): SoundingNote[] {
  const out: SoundingNote[] = [];
  board.forEach((s, i) => {
    if (s.muted || i >= tuning.length) return;
    if (s.open) out.push({ string: i, fret: capo, midi: tuning[i] + capo });
    for (const f of s.frets) if (f > capo) out.push({ string: i, fret: f, midi: tuning[i] + f });
  });
  return out.sort((a, b) => a.midi - b.midi || a.string - b.string);
}

/** Убрать точки, оказавшиеся под каподастром или ниже него. */
export function applyCapo(board: Board, capo: number): Board {
  return board.map((s) => ({ ...s, frets: s.frets.filter((f) => f > capo) }));
}

/**
 * Сдвинуть аппликатуру на semitones полутонов. Открытые струны тоже сдвигаются
 * (становятся зажатыми). Возвращает null, если аппликатура выходит за гриф.
 */
export function transposeBoard(board: Board, semitones: number, capo = 0): Board | null {
  const out: Board = [];
  for (const s of board) {
    const positions = [...(s.open ? [capo] : []), ...s.frets].map((p) => p + semitones);
    if (positions.some((p) => p < capo || p > FRET_COUNT)) return null;
    out.push({
      muted: s.muted,
      open: positions.includes(capo),
      frets: positions.filter((p) => p > capo).sort((a, b) => a - b),
    });
  }
  return out;
}

/** Аппликатура в виде массива: лад на струну (0 — открытая) или null — не играет. */
export type Frets = (number | null)[];

export function boardFromFrets(frets: Frets, capo = 0): Board {
  return frets.map((f) => {
    if (f == null) return { open: false, muted: true, frets: [] };
    if (f <= capo) return { open: true, muted: false, frets: [] };
    return { open: false, muted: false, frets: [f] };
  });
}

/**
 * Раскладывает набор MIDI-нот на гриф (например, аккорд, сыгранный на MIDI-клавиатуре).
 * Ищет удобную аппликатуру: по одной ноте на струну, минимальный разброс ладов.
 * Если так разложить нельзя (нот больше, чем струн, или не хватает диапазона) — ставит каждую ноту
 * в самую низкую доступную позицию, допуская несколько точек на струне.
 */
export function boardFromMidi(notes: number[], tuning: number[], capo = 0): Board {
  const uniq = [...new Set(notes)].sort((a, b) => a - b);
  const n = tuning.length;
  const board = emptyBoard(n);
  if (uniq.length === 0) return board;

  let best: { assign: number[]; cost: number } | null = null;
  if (uniq.length <= n) {
    const assign: number[] = new Array(uniq.length).fill(-1);
    const used = new Set<number>();
    const search = (k: number) => {
      if (k === uniq.length) {
        const frets = assign.map((s, j) => uniq[j] - tuning[s]);
        const fretted = frets.filter((f) => f > capo);
        const span = fretted.length ? Math.max(...fretted) - Math.min(...fretted) : 0;
        if (span > 4 && fretted.length > 1) return;
        const pos = fretted.length ? Math.min(...fretted) : 0;
        // Перекрещивание струн (высокая нота на более низкой струне) — неудобно, но возможно.
        let crossings = 0;
        for (let j = 1; j < assign.length; j++) if (tuning[assign[j]] < tuning[assign[j - 1]]) crossings++;
        const cost = span * 10 + pos + crossings * 30;
        if (!best || cost < best.cost) best = { assign: [...assign], cost };
        return;
      }
      for (let s = 0; s < n; s++) {
        if (used.has(s)) continue;
        const fret = uniq[k] - tuning[s];
        if (fret < capo || fret > FRET_COUNT) continue;
        assign[k] = s;
        used.add(s);
        search(k + 1);
        used.delete(s);
        assign[k] = -1;
      }
    };
    search(0);
  }

  if (best) {
    const { assign } = best as { assign: number[] };
    assign.forEach((s, j) => {
      const fret = uniq[j] - tuning[s];
      if (fret === capo) board[s].open = true;
      else board[s].frets.push(fret);
    });
    board.forEach((s) => {
      if (!s.open && s.frets.length === 0) s.muted = true;
    });
    return board;
  }

  for (const note of uniq) {
    let placed = false;
    for (let s = n - 1; s >= 0 && !placed; s--) {
      const fret = note - tuning[s];
      if (fret < capo || fret > FRET_COUNT) continue;
      if (fret === capo) board[s].open = true;
      else if (!board[s].frets.includes(fret)) board[s].frets.push(fret);
      placed = true;
    }
  }
  board.forEach((s) => s.frets.sort((a, b) => a - b));
  return board;
}

/** Минимальная и максимальная ноты, доступные на грифе. */
export function instrumentRange(tuning: number[]): [number, number] {
  return [Math.min(...tuning), Math.max(...tuning) + FRET_COUNT];
}

/** Подогнать число струн доски под строй (при смене инструмента). */
export function fitBoard(board: Board, strings: number): Board {
  if (board.length === strings) return board;
  return emptyBoard(strings);
}
