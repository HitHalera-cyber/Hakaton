// Производные данные инструмента: строй, звучащие ноты, определённый аккорд, аппликатура.
// Чистая функция от состояния с запоминанием последнего результата — её зовут и хуки, и действия.

import { detectChord, type DetectionResult } from '../core/music/chords';
import { computeFingering, type Fingering } from '../core/music/fingering';
import { instrumentRange, soundingNotes, type Board, type SoundingNote } from '../core/music/fretboard';
import { MAX_CAPO, getTuning, type Tuning } from '../core/music/tunings';

export interface ChordRef {
  rootPc: number;
  templateId: string;
  bassPc?: number;
}

export interface GuitarModel {
  tuning: Tuning;
  strings: number[];
  capo: number;
  range: [number, number];
  boardNotes: SoundingNote[];
  /** Откуда ноты: с грифа или с MIDI-клавиатуры. */
  source: 'board' | 'midi';
  /** Звучащие ноты (MIDI) по возрастанию. */
  activeMidi: number[];
  result: DetectionResult;
  /** Название формы без учёта каподастра (например, «G» при звучании A). */
  shapeSymbol?: string;
  fingering: Fingering;
  chordRef?: ChordRef;
}

interface Inputs {
  board: Board;
  tuningId: string;
  customStrings: number[];
  capo: number;
  midiHeld: number[];
  midiLatched: number[];
}

let last: { inputs: Inputs; model: GuitarModel } | null = null;

const same = (a: Inputs, b: Inputs) =>
  a.board === b.board &&
  a.tuningId === b.tuningId &&
  a.customStrings === b.customStrings &&
  a.capo === b.capo &&
  a.midiHeld === b.midiHeld &&
  a.midiLatched === b.midiLatched;

export function guitarModel(inputs: Inputs): GuitarModel {
  if (last && same(last.inputs, inputs)) return last.model;
  const tuning = getTuning(inputs.tuningId, inputs.customStrings);
  const strings = tuning.strings;
  const capo = Math.min(inputs.capo, MAX_CAPO);
  const boardNotes = soundingNotes(inputs.board, strings, capo);
  const midi = [...new Set([...inputs.midiHeld, ...inputs.midiLatched])].sort((a, b) => a - b);
  const source: 'board' | 'midi' = midi.length > 0 ? 'midi' : 'board';
  const activeMidi = source === 'midi' ? midi : boardNotes.map((n) => n.midi);
  const result = detectChord(activeMidi);
  const p = result.kind === 'chord' ? result.primary : undefined;
  const model: GuitarModel = {
    tuning,
    strings,
    capo,
    range: instrumentRange(strings.map((s) => s + capo)),
    boardNotes,
    source,
    activeMidi,
    result,
    shapeSymbol: capo > 0 && source === 'board' ? detectChord(activeMidi.map((m) => m - capo)).primary?.symbol : undefined,
    fingering: computeFingering(inputs.board, capo),
    chordRef: p ? { rootPc: p.rootPc, templateId: p.template.id, bassPc: p.bassPc !== p.rootPc ? p.bassPc : undefined } : undefined,
  };
  last = { inputs, model };
  return model;
}
