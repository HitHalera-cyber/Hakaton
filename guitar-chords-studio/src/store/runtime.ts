// Состояние сеанса (не сохраняется, кроме окон): уведомления, выдвижная панель, след на круге,
// прослушивание гитары, проигрывание последовательности, MIDI-устройства, режим разбора песни.

import type { RecognizedChord } from '../core/analysis/chordRecognition';
import type { HeardNotes, SoundResult } from '../core/analysis/liveSound';
import type { Frets } from '../core/music/fretboard';
import type { MidiDevice } from '../core/midi/midiInput';
import type { ModuleId } from '../modules/ids';
import type { Slice } from './types';

export interface TrailChord {
  rootPc: number;
  templateId: string;
  symbol: string;
  nameRu: string;
  source: 'board' | 'midi' | 'guitar' | 'song';
  id: number;
}

export type HoldState = 'idle' | 'listening' | 'done' | 'short';
export type MidiStatus = 'init' | 'ready' | 'denied' | 'unavailable' | 'unsupported';

export interface StringsRuntime {
  /** Щипки по порядку: нота или null (глухой). */
  plucks: (number | null)[];
  result: { frets: Frets; tab: string; symbol: string; nameRu: string; confidence: number } | null;
}

export interface ListenRuntime {
  active: boolean;
  error: string;
  level: number;
  result: SoundResult | null;
  /** Строй гитары относительно A = 440 Гц, центы (оценка по звуку). */
  tuningCents: number;
  /** Шум комнаты уже измерен (пока гитара молчала). */
  noiseReady: boolean;
  /** Итоговое усиление микрофона (с учётом автоусиления). */
  gainNow: number;
  chroma: number[];
  history: RecognizedChord[];
  /** Режим «По струнам»: услышанные щипки и итоговая аппликатура. */
  strings: StringsRuntime;
  /** Нейросеть: не нужна / загружается / готова / считает / ошибка. */
  neural: 'off' | 'loading' | 'ready' | 'busy' | 'error';
  /** Сколько миллисекунд нейросеть думала над последним ударом и на чём считает. */
  neuralMs: number;
  neuralBackend: string;
  /** Когда шумодав последний раз отсеял посторонний звук (мс). */
  ignoredAt: number;
  /** Последняя услышанная нота или интервал (когда звучит не аккорд). */
  heardNotes: HeardNotes | null;
  hold: { state: HoldState; progress: number };
}

export interface RuntimeSlice {
  toastText: string | null;
  toast: (text: string) => void;
  aboutOpen: boolean;
  setAboutOpen: (v: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  drawerOpen: boolean;
  /** Открыть раздел: в «Классике» — справа от аккорда, в других раскладках — в выдвижной панели. */
  openModule: (id: ModuleId) => void;
  closeDrawer: () => void;

  trail: TrailChord[];
  pushTrail: (c: Omit<TrailChord, 'id'>) => void;
  clearTrail: () => void;

  libRequest: { rootPc: number; templateId: string; bassPc?: number; nonce: number } | null;
  showVoicings: (ref: { rootPc: number; templateId: string; bassPc?: number }) => void;

  /** Сколько панелей разбора песни открыто сейчас; пока > 0, гриф показывает только аккорды песни. */
  songOpen: number;
  songPlaying: boolean;
  setSongOpen: (open: boolean) => void;
  setSongPlaying: (v: boolean) => void;

  listen: ListenRuntime;
  setListen: (p: Partial<ListenRuntime>) => void;

  metro: { running: boolean; beat: number };
  setMetro: (p: Partial<{ running: boolean; beat: number }>) => void;

  seq: { playing: boolean; current: number | null };
  setSeq: (p: Partial<{ playing: boolean; current: number | null }>) => void;

  midiIO: { status: MidiStatus; error?: string; devices: MidiDevice[]; outputs: MidiDevice[] };
  setMidiIO: (p: Partial<RuntimeSlice['midiIO']>) => void;
}

let trailId = 0;
let toastTimer = 0;

export const createRuntimeSlice: Slice<RuntimeSlice> = (set, get) => ({
  toastText: null,
  toast: (text) => {
    set({ toastText: text });
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => set({ toastText: null }), 2600);
  },
  aboutOpen: false,
  setAboutOpen: (aboutOpen) => set({ aboutOpen }),
  paletteOpen: false,
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
  drawerOpen: false,
  openModule: (tab) => {
    get().patchView({ tab });
    if (get().settings.view.layout !== 'classic') set({ drawerOpen: true });
  },
  closeDrawer: () => set({ drawerOpen: false }),

  trail: [],
  pushTrail: (c) => set((s) => (s.trail[0]?.symbol === c.symbol ? {} : { trail: [{ ...c, id: ++trailId }, ...s.trail].slice(0, 12) })),
  clearTrail: () => set({ trail: [] }),

  libRequest: null,
  showVoicings: (ref) => {
    set({ libRequest: { ...ref, nonce: Date.now() } });
    get().openModule('library');
  },

  songOpen: 0,
  songPlaying: false,
  setSongOpen: (open) => set((s) => ({ songOpen: Math.max(0, s.songOpen + (open ? 1 : -1)) })),
  setSongPlaying: (songPlaying) => set({ songPlaying }),

  listen: {
    active: false,
    error: '',
    level: 0,
    result: null,
    tuningCents: 0,
    noiseReady: false,
    gainNow: 1,
    chroma: new Array(12).fill(0),
    history: [],
    heardNotes: null,
    strings: { plucks: [], result: null },
    neural: 'off',
    neuralMs: 0,
    neuralBackend: '',
    ignoredAt: 0,
    hold: { state: 'idle', progress: 0 },
  },
  setListen: (p) => set((s) => ({ listen: { ...s.listen, ...p } })),

  metro: { running: false, beat: -1 },
  setMetro: (p) => set((s) => ({ metro: { ...s.metro, ...p } })),

  seq: { playing: false, current: null },
  setSeq: (p) => set((s) => ({ seq: { ...s.seq, ...p } })),

  midiIO: { status: 'init', devices: [], outputs: [] },
  setMidiIO: (p) => set((s) => ({ midiIO: { ...s.midiIO, ...p } })),
});
