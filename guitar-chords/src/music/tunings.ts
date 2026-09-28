// Строи гитары. Струны перечисляются от 6-й (басовой) к 1-й.

export type TuningId = 'standard' | 'dropD';

export interface Tuning {
  id: TuningId;
  name: string;
  /** MIDI-номера открытых струн, индекс 0 — 6-я струна. */
  strings: number[];
}

export const TUNINGS: Record<TuningId, Tuning> = {
  standard: { id: 'standard', name: 'Standard (E A D G B e)', strings: [40, 45, 50, 55, 59, 64] },
  dropD: { id: 'dropD', name: 'Drop D (D A D G B e)', strings: [38, 45, 50, 55, 59, 64] },
};

export const FRET_COUNT = 15;
export const STRING_COUNT = 6;
