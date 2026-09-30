// Строи инструментов. Струны перечисляются от самой низкой (басовой) к самой высокой по положению
// на грифе: для гитары индекс 0 — 6-я струна.

export type Instrument = 'guitar' | 'bass' | 'ukulele';

export interface Tuning {
  id: string;
  name: string;
  group: string;
  instrument: Instrument;
  /** MIDI-номера открытых струн. */
  strings: number[];
}

export const TUNING_LIST: Tuning[] = [
  { id: 'standard', name: 'Standard (E A D G B E)', group: 'Гитара', instrument: 'guitar', strings: [40, 45, 50, 55, 59, 64] },
  { id: 'halfDown', name: 'На полтона ниже (Eb)', group: 'Гитара', instrument: 'guitar', strings: [39, 44, 49, 54, 58, 63] },
  { id: 'dropD', name: 'Drop D (D A D G B E)', group: 'Гитара', instrument: 'guitar', strings: [38, 45, 50, 55, 59, 64] },
  { id: 'dropC', name: 'Drop C (C G C F A D)', group: 'Гитара', instrument: 'guitar', strings: [36, 43, 48, 53, 57, 62] },
  { id: 'openG', name: 'Open G (D G D G B D)', group: 'Гитара', instrument: 'guitar', strings: [38, 43, 50, 55, 59, 62] },
  { id: 'openD', name: 'Open D (D A D F# A D)', group: 'Гитара', instrument: 'guitar', strings: [38, 45, 50, 54, 57, 62] },
  { id: 'openE', name: 'Open E (E B E G# B E)', group: 'Гитара', instrument: 'guitar', strings: [40, 47, 52, 56, 59, 64] },
  { id: 'dadgad', name: 'DADGAD', group: 'Гитара', instrument: 'guitar', strings: [38, 45, 50, 55, 57, 62] },
  { id: 'seven', name: '7-струнная (B E A D G B E)', group: 'Гитара', instrument: 'guitar', strings: [35, 40, 45, 50, 55, 59, 64] },
  { id: 'custom', name: 'Свой строй…', group: 'Гитара', instrument: 'guitar', strings: [40, 45, 50, 55, 59, 64] },
  { id: 'bass4', name: 'Бас 4 струны (E A D G)', group: 'Бас-гитара', instrument: 'bass', strings: [28, 33, 38, 43] },
  { id: 'bass5', name: 'Бас 5 струн (B E A D G)', group: 'Бас-гитара', instrument: 'bass', strings: [23, 28, 33, 38, 43] },
  { id: 'ukulele', name: 'Укулеле (G C E A)', group: 'Укулеле', instrument: 'ukulele', strings: [67, 60, 64, 69] },
];

export const TUNINGS: Record<string, Tuning> = Object.fromEntries(TUNING_LIST.map((t) => [t.id, t]));

export function getTuning(id: string, customStrings?: number[]): Tuning {
  const t = TUNINGS[id] ?? TUNINGS.standard;
  if (t.id === 'custom' && customStrings?.length) return { ...t, strings: customStrings };
  return t;
}

export const FRET_COUNT = 15;
export const MAX_CAPO = 12;
