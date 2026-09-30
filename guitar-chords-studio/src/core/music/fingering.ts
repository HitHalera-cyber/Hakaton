// Подсказка аппликатуры пальцами левой руки: 1 — указательный … 4 — мизинец.
// Эвристика: самый нижний лад — указательный (при нескольких нотах на нём — баррэ),
// остальные пальцы по возрастанию ладов («один палец — один лад»).

import type { Board } from './fretboard';

export interface Barre {
  fret: number;
  fromString: number;
  toString: number;
}

export interface Fingering {
  /** Ключ «струна-лад» → номер пальца. */
  fingers: Map<string, number>;
  barre: Barre | null;
  warnings: string[];
  /** Сколько пальцев нужно. */
  count: number;
}

export const fingerKey = (s: number, f: number) => `${s}-${f}`;

export function computeFingering(board: Board, capo = 0): Fingering {
  const notes: { s: number; f: number }[] = [];
  const warnings: string[] = [];
  board.forEach((st, s) => {
    if (st.muted) return;
    const frets = st.frets.filter((f) => f > capo);
    if (frets.length > 1) warnings.push('На одной струне несколько точек — так одной рукой не сыграть');
    for (const f of frets) notes.push({ s, f });
  });
  const fingers = new Map<string, number>();
  if (notes.length === 0) return { fingers, barre: null, warnings: [], count: 0 };

  const minF = Math.min(...notes.map((n) => n.f));
  const maxF = Math.max(...notes.map((n) => n.f));
  const atMin = notes.filter((n) => n.f === minF);

  // Баррэ: несколько нот на нижнем ладу и иначе не хватает пальцев (или нот на нём ≥ 3).
  let barre: Barre | null = null;
  if (atMin.length >= 2 && (notes.length > 4 || atMin.length >= 3)) {
    const from = Math.min(...atMin.map((n) => n.s));
    const to = Math.max(...atMin.map((n) => n.s));
    let ok = true;
    for (let s = from; s <= to; s++) {
      const st = board[s];
      // Открытая струна внутри баррэ оказалась бы зажатой — баррэ невозможно.
      if (st.open && !st.muted && !st.frets.some((f) => f > capo)) ok = false;
    }
    if (ok) barre = { fret: minF, fromString: from, toString: to };
  }

  const byOrder = (a: { s: number; f: number }, b: { s: number; f: number }) => a.f - b.f || a.s - b.s;
  let count: number;
  if (barre) {
    atMin.forEach((n) => fingers.set(fingerKey(n.s, n.f), 1));
    const rest = notes.filter((n) => n.f !== minF).sort(byOrder);
    let last = 1;
    for (const n of rest) {
      const finger = Math.max(last + 1, 1 + n.f - minF);
      fingers.set(fingerKey(n.s, n.f), finger);
      last = finger;
    }
    count = 1 + rest.length;
  } else {
    const sorted = [...notes].sort(byOrder);
    let last = 0;
    const assigned = sorted.map((n) => {
      const finger = Math.max(last + 1, 1 + n.f - minF);
      last = finger;
      return finger;
    });
    // Если «палец на лад» даёт номер больше 4, но нот не больше 4 — просто пронумеровать подряд.
    if (Math.max(...assigned) > 4 && sorted.length <= 4) assigned.forEach((_, i) => (assigned[i] = i + 1));
    sorted.forEach((n, i) => fingers.set(fingerKey(n.s, n.f), assigned[i]));
    count = sorted.length;
  }

  if (count > 4) warnings.push(`Нужно ${count} пальцев — больше, чем есть на руке`);
  const span = maxF - minF;
  if (span >= 5) warnings.push(`Очень широкая растяжка: ${span + 1} ладов`);
  else if (span === 4) warnings.push('Широкая растяжка: 5 ладов — трудно');
  for (const [k, f] of fingers) if (f > 4) fingers.set(k, 4);

  return { fingers, barre, warnings: [...new Set(warnings)], count };
}
