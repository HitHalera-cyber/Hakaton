// Гриф и MIDI-ноты: состояние и действия. Производные данные — в guitarModel.ts.

import { audio, type ChordNote } from '../core/audio/engine';
import { CHORD_TEMPLATES } from '../core/music/chords';
import {
  applyCapo,
  boardFromFrets,
  boardFromMidi,
  emptyBoard,
  isBoardEmpty,
  soundingNotes,
  transposeBoard,
  type Board,
  type Frets,
} from '../core/music/fretboard';
import { getTuning } from '../core/music/tunings';
import { generateVoicings } from '../core/music/voicings';
import { guitarModel, type GuitarModel } from './guitarModel';
import type { AppState, Slice } from './types';

export interface CellFlash {
  s: number;
  f: number;
  ok: boolean;
}

export interface GuitarSlice {
  board: Board;
  midiHeld: number[];
  midiLatched: number[];
  flash: CellFlash | null;

  /** Производные данные (строй, аккорд, аппликатура). */
  guitar: () => GuitarModel;
  setBoard: (b: Board) => void;
  /** Поставить доску и (по настройке) сыграть её. */
  apply: (b: Board, play?: boolean) => void;
  /** Правка мышью: MIDI-ноты сбрасываются, определение возвращается к грифу. */
  edit: (b: Board) => void;
  loadFrets: (frets: Frets, play?: boolean) => void;
  voicingFor: (rootPc: number, templateId: string, bassPc?: number) => Frets | null;
  /** Поставить аккорд удобной аппликатурой без звука (играет песня или гитарист). */
  showChord: (rootPc: number, templateId: string, bassPc?: number) => void;
  clearBoard: () => void;
  transpose: (k: number) => void;
  setCapo: (c: number) => void;
  setTuning: (id: string) => void;
  loadShape: (board: Board, tuningId: string, strings: number[], capo: number) => void;
  currentNotes: () => ChordNote[];
  currentBoard: () => Board;
  currentSymbol: () => string;
  play: () => void;
  playNotes: (notes: ChordNote[]) => void;
  setFlash: (f: CellFlash | null) => void;

  midiNoteOn: (note: number) => void;
  midiNoteOff: (note: number) => void;
  toggleMidiKey: (note: number) => void;
  clearMidi: () => void;
}

export const modelOf = (s: AppState) =>
  guitarModel({
    board: s.board,
    tuningId: s.settings.view.tuning,
    customStrings: s.settings.view.customStrings,
    capo: s.settings.view.capo,
    midiHeld: s.midiHeld,
    midiLatched: s.midiLatched,
  });

export const createGuitarSlice: Slice<GuitarSlice> = (set, get) => {
  const notesOf = (b: Board): ChordNote[] => {
    const g = get().guitar();
    return soundingNotes(b, g.strings, g.capo).map((n) => ({ midi: n.midi, string: n.string }));
  };
  const clearMidiIfAny = () => {
    if (get().midiHeld.length || get().midiLatched.length) set({ midiHeld: [], midiLatched: [] });
  };

  return {
    board: emptyBoard(),
    midiHeld: [],
    midiLatched: [],
    flash: null,

    guitar: () => modelOf(get()),
    setBoard: (board) => set({ board }),
    playNotes: (notes) => {
      const { mode, arpStepMs } = get().settings.sound;
      audio.playChord(notes, mode, arpStepMs);
    },
    apply: (board, play = get().settings.sound.autoPlay) => {
      set({ board });
      if (play) get().playNotes(notesOf(board));
    },
    edit: (board) => {
      clearMidiIfAny();
      get().apply(board);
    },
    loadFrets: (frets, play = true) => {
      clearMidiIfAny();
      get().apply(boardFromFrets(frets, get().guitar().capo), play);
    },
    voicingFor: (rootPc, templateId, bassPc) => {
      const t = CHORD_TEMPLATES.find((x) => x.id === templateId);
      if (!t) return null;
      const { strings, capo } = get().guitar();
      return (
        generateVoicings(rootPc, t, strings, { capo, bassPc, limit: 1 })[0]?.frets ??
        generateVoicings(rootPc, t, strings, { capo, limit: 1 })[0]?.frets ??
        null
      );
    },
    showChord: (rootPc, templateId, bassPc) => {
      const frets = get().voicingFor(rootPc, templateId, bassPc);
      if (frets) get().loadFrets(frets, false);
    },
    clearBoard: () => {
      audio.stopAll();
      set({ midiHeld: [], midiLatched: [], board: emptyBoard(get().guitar().strings.length) });
    },
    transpose: (k) => {
      const g = get().guitar();
      if (g.source === 'midi') return set((s) => ({ midiLatched: s.midiLatched.map((m) => m + k) }));
      if (isBoardEmpty(get().board)) return;
      const next = transposeBoard(get().board, k, g.capo);
      if (!next) return get().toast(k > 0 ? 'Выше нельзя: аппликатура выйдет за 15-й лад' : 'Ниже нельзя: аппликатура упирается в порожек');
      get().apply(next);
    },
    setCapo: (capo) => {
      get().patchView({ capo });
      set((s) => ({ board: applyCapo(s.board, capo) }));
    },
    setTuning: (id) => {
      const next = getTuning(id, get().settings.view.customStrings);
      get().patchView({ tuning: id, capo: next.instrument === 'guitar' ? get().settings.view.capo : 0 });
      if (get().board.length !== next.strings.length) set({ board: emptyBoard(next.strings.length) });
    },
    loadShape: (board, tuningId, strings, capo) => {
      clearMidiIfAny();
      if (tuningId === 'custom') get().patchView({ tuning: tuningId, customStrings: strings, capo });
      else get().patchView({ tuning: tuningId, capo });
      set({ board });
      get().playNotes(soundingNotes(board, strings, capo).map((n) => ({ midi: n.midi, string: n.string })));
    },
    currentNotes: () => {
      const g = get().guitar();
      return g.source === 'board' ? notesOf(get().board) : g.activeMidi.map((midi) => ({ midi }));
    },
    currentBoard: () => {
      const g = get().guitar();
      return g.source === 'midi' ? boardFromMidi(g.activeMidi, g.strings, g.capo) : get().board;
    },
    currentSymbol: () => {
      const r = get().guitar().result;
      return r.primary?.symbol ?? (r.noteNames.join('-') || 'аккорд');
    },
    play: () => get().playNotes(get().currentNotes()),
    setFlash: (flash) => set({ flash }),

    midiNoteOn: (note) =>
      set((s) => {
        const wasEmpty = s.midiHeld.length === 0;
        const midiHeld = s.midiHeld.includes(note) ? s.midiHeld : [...s.midiHeld, note];
        // Новый аккорд начинается, когда все клавиши были отпущены.
        const midiLatched = !s.settings.midi.latch ? s.midiLatched : wasEmpty ? [note] : [...new Set([...s.midiLatched, note])];
        return { midiHeld, midiLatched };
      }),
    midiNoteOff: (note) => set((s) => (s.midiHeld.includes(note) ? { midiHeld: s.midiHeld.filter((n) => n !== note) } : {})),
    toggleMidiKey: (note) =>
      set((s) => {
        if (s.midiLatched.includes(note)) return { midiLatched: s.midiLatched.filter((n) => n !== note) };
        audio.playNote(note, 0.8);
        return { midiLatched: [...s.midiLatched, note] };
      }),
    clearMidi: () => set({ midiHeld: [], midiLatched: [] }),
  };
};
