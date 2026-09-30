// Базовые понятия: высотные классы (0 = C ... 11 = B), написание нот буквами и по-русски.

export const LETTERS = ['C', 'D', 'E', 'F', 'G', 'A', 'B'] as const;
export const LETTER_PC = [0, 2, 4, 5, 7, 9, 11] as const;
export const LETTER_RU = ['До', 'Ре', 'Ми', 'Фа', 'Соль', 'Ля', 'Си'] as const;

/** Нота с конкретным написанием: буква (0..6) + альтерация (-2..2). */
export interface Spelled {
  letter: number;
  acc: number;
}

export const mod12 = (n: number) => ((n % 12) + 12) % 12;

export function spelledPc(s: Spelled): number {
  return mod12(LETTER_PC[s.letter] + s.acc);
}

const ACC_SYMBOL: Record<number, string> = { [-2]: 'bb', [-1]: 'b', 0: '', 1: '#', 2: '##' };
const ACC_RU: Record<number, string> = { [-2]: '-дубль-бемоль', [-1]: '-бемоль', 0: '', 1: '-диез', 2: '-дубль-диез' };

export function spelledName(s: Spelled): string {
  return LETTERS[s.letter] + ACC_SYMBOL[s.acc];
}

export function spelledRu(s: Spelled): string {
  return LETTER_RU[s.letter] + ACC_RU[s.acc];
}

/** Написание по умолчанию — привычное гитаристам: C# и F#, но Eb, Ab, Bb. */
const DEFAULT_SPELLING: Spelled[] = [
  { letter: 0, acc: 0 }, // C
  { letter: 0, acc: 1 }, // C#
  { letter: 1, acc: 0 }, // D
  { letter: 2, acc: -1 }, // Eb
  { letter: 2, acc: 0 }, // E
  { letter: 3, acc: 0 }, // F
  { letter: 3, acc: 1 }, // F#
  { letter: 4, acc: 0 }, // G
  { letter: 5, acc: -1 }, // Ab
  { letter: 5, acc: 0 }, // A
  { letter: 6, acc: -1 }, // Bb
  { letter: 6, acc: 0 }, // B
];

export function defaultSpelling(pc: number): Spelled {
  return DEFAULT_SPELLING[mod12(pc)];
}

export function pcName(pc: number): string {
  return spelledName(defaultSpelling(pc));
}

export function pcNameRu(pc: number): string {
  return spelledRu(defaultSpelling(pc));
}

export function midiOctave(midi: number): number {
  return Math.floor(midi / 12) - 1;
}

/** Например 64 → «E4». */
export function midiName(midi: number): string {
  return pcName(midi) + midiOctave(midi);
}

export function midiToFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

/** Нота, отстоящая от spelled на заданное число ступеней (буквенно) и полутонов. */
export function spellInterval(root: Spelled, letterSteps: number, semitones: number): Spelled {
  const letter = (root.letter + letterSteps) % 7;
  const target = mod12(spelledPc(root) + semitones);
  let acc = mod12(target - LETTER_PC[letter]);
  if (acc > 6) acc -= 12;
  if (acc < -2 || acc > 2) return defaultSpelling(target);
  return { letter, acc };
}

export const INTERVAL_RU = [
  'унисон / октава',
  'малая секунда',
  'большая секунда',
  'малая терция',
  'большая терция',
  'чистая кварта',
  'тритон',
  'чистая квинта',
  'малая секста',
  'большая секста',
  'малая септима',
  'большая септима',
];
