// Гаммы и лады, аккорды тональности (диатонические) и популярные последовательности.

import { CHORD_TEMPLATES, type ChordTemplate } from './chords';
import { defaultSpelling, mod12, spellInterval, spelledName, spelledRu, type Spelled } from './notes';

export interface Scale {
  id: string;
  name: string;
  /** Интервалы от тоники в полутонах. */
  steps: number[];
  /** Ступени для подписи: '1', 'b3'… */
  degrees: string[];
}

export const SCALES: Scale[] = [
  { id: 'major', name: 'Мажор (ионийский)', steps: [0, 2, 4, 5, 7, 9, 11], degrees: ['1', '2', '3', '4', '5', '6', '7'] },
  { id: 'minor', name: 'Натуральный минор (эолийский)', steps: [0, 2, 3, 5, 7, 8, 10], degrees: ['1', '2', 'b3', '4', '5', 'b6', 'b7'] },
  { id: 'harmMinor', name: 'Гармонический минор', steps: [0, 2, 3, 5, 7, 8, 11], degrees: ['1', '2', 'b3', '4', '5', 'b6', '7'] },
  { id: 'melMinor', name: 'Мелодический минор', steps: [0, 2, 3, 5, 7, 9, 11], degrees: ['1', '2', 'b3', '4', '5', '6', '7'] },
  { id: 'pentMajor', name: 'Мажорная пентатоника', steps: [0, 2, 4, 7, 9], degrees: ['1', '2', '3', '5', '6'] },
  { id: 'pentMinor', name: 'Минорная пентатоника', steps: [0, 3, 5, 7, 10], degrees: ['1', 'b3', '4', '5', 'b7'] },
  { id: 'blues', name: 'Блюзовая гамма', steps: [0, 3, 5, 6, 7, 10], degrees: ['1', 'b3', '4', 'b5', '5', 'b7'] },
  { id: 'dorian', name: 'Дорийский лад', steps: [0, 2, 3, 5, 7, 9, 10], degrees: ['1', '2', 'b3', '4', '5', '6', 'b7'] },
  { id: 'phrygian', name: 'Фригийский лад', steps: [0, 1, 3, 5, 7, 8, 10], degrees: ['1', 'b2', 'b3', '4', '5', 'b6', 'b7'] },
  { id: 'lydian', name: 'Лидийский лад', steps: [0, 2, 4, 6, 7, 9, 11], degrees: ['1', '2', '3', '#4', '5', '6', '7'] },
  { id: 'mixolydian', name: 'Миксолидийский лад', steps: [0, 2, 4, 5, 7, 9, 10], degrees: ['1', '2', '3', '4', '5', '6', 'b7'] },
  { id: 'locrian', name: 'Локрийский лад', steps: [0, 1, 3, 5, 6, 8, 10], degrees: ['1', 'b2', 'b3', '4', 'b5', 'b6', 'b7'] },
  { id: 'chromatic', name: 'Хроматическая', steps: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], degrees: ['1', 'b2', '2', 'b3', '3', '4', 'b5', '5', 'b6', '6', 'b7', '7'] },
];

/** Высотный класс → ступень гаммы. */
export function scaleDegrees(rootPc: number, scale: Scale): Map<number, string> {
  return new Map(scale.steps.map((s, i) => [mod12(rootPc + s), scale.degrees[i]]));
}

/** Написание ноты по ступени гаммы (A минор: A B C D E F G; F мажор: … Bb). */
export function scaleNoteNames(rootPc: number, scale: Scale): string[] {
  const root = defaultSpelling(rootPc);
  if (scale.steps.length !== 7) return scale.steps.map((s) => spelledName(defaultSpelling(rootPc + s)));
  return scale.steps.map((s, i) => spelledName(spellInterval(root, i, s)));
}

// ---------- Тональность ----------

export type KeyMode = 'major' | 'minor';

export interface KeyChord {
  degree: number;
  roman: string;
  root: Spelled;
  rootPc: number;
  template: ChordTemplate;
  symbol: string;
  nameRu: string;
  /** Функция: Т, S, D. */
  func: string;
}

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];
const FUNC_MAJOR = ['T', 'S', 'T', 'S', 'D', 'T', 'D'];
const FUNC_MINOR = ['T', 'S', 'T', 'S', 'D', 'S', 'D'];

/** Предпочтительное написание тоники тональности (F, Bb, Eb, но F#, C#m). */
export function keyRootSpelling(pc: number, mode: KeyMode): Spelled {
  if (mode === 'minor') {
    const minor: Record<number, Spelled> = { 1: { letter: 0, acc: 1 }, 3: { letter: 2, acc: -1 }, 6: { letter: 3, acc: 1 }, 8: { letter: 4, acc: 1 }, 10: { letter: 6, acc: -1 } };
    return minor[pc] ?? defaultSpelling(pc);
  }
  const major: Record<number, Spelled> = { 1: { letter: 1, acc: -1 }, 6: { letter: 3, acc: 1 } };
  return major[pc] ?? defaultSpelling(pc);
}

export function keyChords(tonicPc: number, mode: KeyMode, sevenths: boolean): KeyChord[] {
  const scale = mode === 'major' ? SCALES[0] : SCALES[1];
  const tonic = keyRootSpelling(tonicPc, mode);
  const notes = scale.steps.map((s, i) => ({ pc: mod12(tonicPc + s), spelled: spellInterval(tonic, i, s) }));
  return notes.map((root, i) => {
    const third = mod12(notes[(i + 2) % 7].pc - root.pc);
    const fifth = mod12(notes[(i + 4) % 7].pc - root.pc);
    const seventh = mod12(notes[(i + 6) % 7].pc - root.pc);
    let id: string;
    if (!sevenths) id = third === 4 ? (fifth === 8 ? 'aug' : 'maj') : fifth === 6 ? 'dim' : 'min';
    else if (third === 4) id = seventh === 11 ? 'maj7' : '7';
    else if (fifth === 6) id = seventh === 10 ? 'm7b5' : 'dim7';
    else id = seventh === 11 ? 'mMaj7' : 'm7';
    const template = CHORD_TEMPLATES.find((t) => t.id === id)!;
    const minorish = third === 3;
    let roman = minorish ? ROMAN[i].toLowerCase() : ROMAN[i];
    if (id === 'm7b5') roman += 'ø7';
    else if (fifth === 6) roman += sevenths ? '°7' : '°';
    else if (sevenths) roman += id === 'maj7' ? 'maj7' : '7';
    return {
      degree: i,
      roman,
      root: root.spelled,
      rootPc: root.pc,
      template,
      symbol: spelledName(root.spelled) + template.suffix,
      nameRu: `${spelledRu(root.spelled)} ${template.ru}`,
      func: (mode === 'major' ? FUNC_MAJOR : FUNC_MINOR)[i],
    };
  });
}

export interface Progression {
  id: string;
  name: string;
  /** Ступени (0 — тоника). */
  degrees: number[];
  mode?: KeyMode;
  /** Играть все аккорды как доминантсептаккорды (блюз). */
  dominant?: boolean;
  /** Использовать септаккорды. */
  sevenths?: boolean;
}

export const PROGRESSIONS: Progression[] = [
  { id: 'pop', name: 'Поп: I – V – vi – IV', degrees: [0, 4, 5, 3], mode: 'major' },
  { id: 'fifties', name: '50-е: I – vi – IV – V', degrees: [0, 5, 3, 4], mode: 'major' },
  { id: 'sad', name: 'Лирическая: vi – IV – I – V', degrees: [5, 3, 0, 4], mode: 'major' },
  { id: 'rock', name: 'Рок: I – IV – V – IV', degrees: [0, 3, 4, 3], mode: 'major' },
  { id: 'jazz', name: 'Джаз: ii7 – V7 – Imaj7', degrees: [1, 4, 0], mode: 'major', sevenths: true },
  { id: 'canon', name: 'Канон Пахельбеля: I – V – vi – iii – IV – I – IV – V', degrees: [0, 4, 5, 2, 3, 0, 3, 4], mode: 'major' },
  { id: 'blues', name: 'Блюз 12 тактов: I7 – IV7 – V7', degrees: [0, 0, 0, 0, 3, 3, 0, 0, 4, 3, 0, 4], mode: 'major', dominant: true },
  { id: 'minorPop', name: 'Минорная: i – VI – III – VII', degrees: [0, 5, 2, 6], mode: 'minor' },
  { id: 'andalusian', name: 'Андалузская каденция: i – VII – VI – V', degrees: [0, 6, 5, 4], mode: 'minor' },
  { id: 'minorBasic', name: 'Минорная классика: i – iv – v – i', degrees: [0, 3, 4, 0], mode: 'minor' },
];

/** Аккорды последовательности в тональности (с поправками: V в миноре мажорная у андалузской). */
export function progressionChords(tonicPc: number, mode: KeyMode, p: Progression): KeyChord[] {
  const chords = keyChords(tonicPc, mode, !!p.sevenths);
  return p.degrees.map((d, i) => {
    let c = chords[d];
    const tweak = (id: string) => {
      const template = CHORD_TEMPLATES.find((t) => t.id === id)!;
      return { ...c, template, symbol: spelledName(c.root) + template.suffix, nameRu: `${spelledRu(c.root)} ${template.ru}` };
    };
    if (p.dominant) c = tweak('7');
    if (p.id === 'andalusian' && i === 3) c = { ...tweak('maj'), roman: 'V' };
    return c;
  });
}
