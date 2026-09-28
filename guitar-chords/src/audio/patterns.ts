// Схемы боя и перебора. Такт 4/4 разбит на 8 восьмых:
//   D — удар вниз, U — удар вверх, B — басовая нота, b — второй бас, A — нота перебора, '-' — пауза.
// Особая схема «once» — один удар в начале каждого аккорда.

import { audio, type ChordNote } from './engine';

export interface StrumPattern {
  id: string;
  name: string;
  steps: string;
}

export const PATTERNS: StrumPattern[] = [
  { id: 'once', name: 'Один удар на аккорд', steps: 'once' },
  { id: 'quarters', name: 'Четверти: ↓ ↓ ↓ ↓', steps: 'D-D-D-D-' },
  { id: 'eighths', name: 'Восьмые: ↓↑↓↑↓↑↓↑', steps: 'DUDUDUDU' },
  { id: 'six', name: 'Бой «шестёрка»: ↓ ↓↑ ↑↓↑', steps: 'D-DU-UDU' },
  { id: 'pop', name: 'Поп: ↓ ↓↑ ↓↑', steps: 'D-DUD-DU' },
  { id: 'country', name: 'Бас + аккорд (кантри)', steps: 'B-D-b-D-' },
  { id: 'arp', name: 'Перебор восьмыми', steps: 'AAAAAAAA' },
];

// Порядок нот для перебора (индексы от баса): бас — верх — середина…
const ARP_ORDER = [0, 3, 2, 3, 1, 3, 2, 3];

/** Сыграть шаг схемы для аккорда в момент time. */
export function playPatternStep(pattern: StrumPattern, notes: ChordNote[], stepInBar: number, isChordStart: boolean, time: number, stepSec: number) {
  if (!notes.length) return;
  const sorted = [...notes].sort((a, b) => a.midi - b.midi);
  if (pattern.steps === 'once') {
    if (isChordStart) audio.strum(sorted, 'down', time);
    return;
  }
  const ch = pattern.steps[stepInBar % pattern.steps.length];
  const hold = stepSec * 2.2;
  switch (ch) {
    case 'D':
      audio.strum(sorted, 'down', time, { velocity: stepInBar % 4 === 0 ? 0.9 : 0.75 });
      break;
    case 'U':
      // Вверх обычно цепляют только верхние струны.
      audio.strum(sorted.slice(-Math.min(4, sorted.length)), 'up', time, { velocity: 0.55 });
      break;
    case 'B':
      audio.playNote(sorted[0].midi, 0.85, time, sorted[0].string != null ? `s${sorted[0].string}` : undefined);
      break;
    case 'b': {
      const n = sorted[Math.min(1, sorted.length - 1)];
      audio.playNote(n.midi, 0.8, time, n.string != null ? `s${n.string}` : undefined);
      break;
    }
    case 'A': {
      const idx = ARP_ORDER[stepInBar % 8] % sorted.length;
      const n = sorted[idx];
      audio.playNote(n.midi, idx === 0 ? 0.85 : 0.7, time, n.string != null ? `s${n.string}` : undefined, hold * 4);
      break;
    }
  }
}
