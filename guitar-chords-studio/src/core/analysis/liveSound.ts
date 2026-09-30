// Что звучит с гитары: одна нота, интервал (две ноты) или аккорд.
// Ноты ищутся в накопленном спектре (с вычитанием обертонов); если различных нот одна-две —
// это нота или интервал, иначе — сравнение хромаграммы с шаблонами аккордов.

import { INTERVAL_RU, midiName, pcName, pcNameRu } from '../music/notes';
import { recognizeChord, type ChordModel, type Recognition } from './chordRecognition';
import { bassSalience, chromaFromNotes, detectNotes } from './dsp';

export interface HeardNotes {
  kind: 'note' | 'interval';
  /** Звучащие ноты (MIDI) снизу вверх. */
  midis: number[];
  /** Крупная подпись: «A3» или «A + E». */
  label: string;
  /** Расшифровка: «Нота ля» / «Интервал: чистая квинта (пауэр-аккорд A5)». */
  nameRu: string;
}

export interface SoundResult extends Recognition {
  /** Одна нота или интервал — тогда best (аккорд) пустой. */
  notes: HeardNotes | null;
}

// Сдвиги обертонов струны (гармоники 2..8) — пик на таком расстоянии выше звучащей ноты
// считается её обертоном, а не отдельной нотой.
const HARMONIC_OFFSETS = [12, 19, 24, 28, 31, 34, 36];
const SEMI_BASE = 24; // MIDI нулевого элемента спектра (SEMI_LO)

/**
 * Отдельно звучащие ноты по пикам спектра: пик — нота, если он заметен и не объясняется
 * обертоном более низкой найденной ноты. Одна нота даёт пики только на своих обертонах,
 * аккорд — пики, которые обертонами не объяснить.
 */
export function significantNotes(semi: Float32Array, share = 0.1): number[] {
  let max = 0;
  for (let i = 0; i < semi.length; i++) if (semi[i] > max) max = semi[i];
  if (max <= 0) return [];
  const notes: number[] = [];
  const peaks: number[] = [];
  for (let i = 1; i < semi.length - 1; i++) {
    const midi = SEMI_BASE + i;
    if (midi < 38 || midi > 90) continue;
    const v = semi[i];
    if (v < max * share || v < semi[i - 1] || v < semi[i + 1]) continue;
    const explained = peaks.some((j) => HARMONIC_OFFSETS.includes(i - j));
    peaks.push(i);
    if (!explained) notes.push(midi);
  }
  return notes;
}

export function recognizeSound(semi: Float32Array, models: ChordModel[]): SoundResult {
  // По одной ноте на название (самая низкая октава): E3 + E4 — это одна нота ми.
  const midis: number[] = [];
  for (const m of significantNotes(semi)) if (!midis.some((x) => x % 12 === m % 12)) midis.push(m);
  if (midis.length === 1) {
    const m = midis[0];
    return {
      best: null,
      alternatives: [],
      notes: { kind: 'note', midis, label: midiName(m), nameRu: `Нота ${pcNameRu(m % 12).toLowerCase()}` },
    };
  }
  if (midis.length === 2) {
    const semis = (midis[1] - midis[0]) % 12;
    const label = midis.map((m) => pcName(m % 12)).join(' + ');
    const power = semis === 7 ? ` (пауэр-аккорд ${pcName(midis[0] % 12)}5)` : '';
    return { best: null, alternatives: [], notes: { kind: 'interval', midis, label, nameRu: `Интервал: ${INTERVAL_RU[semis]}${power}` } };
  }
  const { chroma } = chromaFromNotes(detectNotes(semi));
  return { ...recognizeChord(chroma, bassSalience(semi), models), notes: null };
}
