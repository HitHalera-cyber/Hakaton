// Избранное, история и последовательность аккордов.

import { boardFromFrets, boardFromMidi, type Board, type Frets } from '../core/music/fretboard';
import { TUNINGS } from '../core/music/tunings';
import { uid, type HistoryEntry, type SavedShape, type SeqItem } from './model';
import type { Slice } from './types';

const HISTORY_LIMIT = 40;

export interface CollectionsSlice {
  saved: SavedShape[];
  history: HistoryEntry[];
  sequence: SeqItem[];

  saveCurrent: () => void;
  removeSaved: (id: string) => void;
  renameSaved: (id: string, name: string) => void;
  importSaved: (list: SavedShape[]) => number;
  openShape: (s: { board?: Board; midi?: number[]; tuning?: string; strings?: number[]; capo?: number }) => void;
  recordHistory: () => void;
  clearHistory: () => void;
  setSequence: (items: SeqItem[]) => void;
  addCurrentToSequence: () => void;
  itemsFromFrets: (chords: { symbol: string; frets: Frets; beats?: number }[]) => SeqItem[];
}

/** Записи без строя и каподастра (старый формат) дополняются значениями по умолчанию. */
export function normalizeShape<T extends { tuning?: string; strings?: number[]; capo?: number }>(
  x: T,
): T & { strings: number[]; capo: number; tuning: string } {
  const tuning = x.tuning && TUNINGS[x.tuning] ? x.tuning : 'standard';
  return { ...x, tuning, strings: x.strings ?? TUNINGS[tuning].strings, capo: x.capo ?? 0 };
}

export const createCollectionsSlice: Slice<CollectionsSlice> = (set, get) => {
  const makeItem = (symbol: string, board: Board, beats = 4): SeqItem => {
    const g = get().guitar();
    return { id: uid(), symbol, board, strings: g.strings, capo: g.capo, beats };
  };
  return {
    saved: [],
    history: [],
    sequence: [],

    saveCurrent: () => {
      const s = get();
      const g = s.guitar();
      const symbol = s.currentSymbol();
      set({
        saved: [
          {
            id: uid(),
            name: symbol,
            symbol,
            nameRu: g.result.primary ? g.result.primary.nameRu : 'Неизвестный аккорд',
            tuning: s.settings.view.tuning,
            strings: g.strings,
            capo: g.capo,
            board: s.currentBoard(),
            created: Date.now(),
          },
          ...s.saved,
        ],
      });
      s.toast(`«${symbol}» добавлен в избранное`);
    },
    removeSaved: (id) => set((s) => ({ saved: s.saved.filter((x) => x.id !== id) })),
    renameSaved: (id, name) => set((s) => ({ saved: s.saved.map((x) => (x.id === id ? { ...x, name } : x)) })),
    importSaved: (list) => {
      const valid = list.filter((s) => s && Array.isArray(s.board) && typeof s.symbol === 'string').map(normalizeShape);
      set((s) => {
        const ids = new Set(s.saved.map((x) => x.id));
        return { saved: [...s.saved, ...valid.filter((x) => !ids.has(x.id))] };
      });
      return valid.length;
    },
    openShape: (raw) => {
      const e = normalizeShape(raw);
      if (e.board) get().loadShape(e.board, e.tuning, e.strings, e.capo);
      else if (e.midi) get().loadShape(boardFromMidi(e.midi, e.strings, e.capo), e.tuning, e.strings, e.capo);
    },
    recordHistory: () => {
      const s = get();
      const g = s.guitar();
      const p = g.result.kind === 'chord' ? g.result.primary : undefined;
      if (!p || s.history[0]?.symbol === p.symbol) return;
      const entry: HistoryEntry = {
        id: uid(),
        symbol: p.symbol,
        nameRu: p.nameRu + (p.inversionRu ? `, ${p.inversionRu}` : ''),
        notes: g.result.noteNames,
        time: Date.now(),
        source: g.source,
        tuning: s.settings.view.tuning,
        strings: g.strings,
        capo: g.capo,
        board: g.source === 'board' ? s.board : undefined,
        midi: g.source === 'midi' ? g.activeMidi : undefined,
      };
      set({ history: [entry, ...s.history].slice(0, HISTORY_LIMIT) });
    },
    clearHistory: () => set({ history: [] }),
    setSequence: (sequence) => set({ sequence }),
    addCurrentToSequence: () => {
      const s = get();
      set({ sequence: [...s.sequence, makeItem(s.currentSymbol(), s.currentBoard())] });
      s.toast(`«${s.currentSymbol()}» добавлен в последовательность`);
    },
    itemsFromFrets: (chords) => chords.map((c) => makeItem(c.symbol, boardFromFrets(c.frets, get().guitar().capo), c.beats)),
  };
};
