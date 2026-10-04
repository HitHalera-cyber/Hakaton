// Модель данных приложения: типы и значения по умолчанию. Здесь нет React и побочных эффектов.

import type { Calibration } from '../core/analysis/calibration';
import type { PlayMode, Timbre } from '../core/audio/engine';
import type { Board, Frets } from '../core/music/fretboard';
import { TUNINGS } from '../core/music/tunings';
import type { ModuleId } from '../modules/ids';

export type DotLabel = 'note' | 'degree' | 'finger';
export type LayoutId = 'classic' | 'dashboard' | 'listener';

export interface ViewSettings {
  theme: string;
  layout: LayoutId;
  /** Разделы в плитках приборной панели. */
  tiles: ModuleId[];
  showNotes: boolean;
  dotLabel: DotLabel;
  tuning: string;
  customStrings: number[];
  capo: number;
  tab: ModuleId;
  /** Тональность для квинтового круга: 'auto' или «позиция-лад». */
  circleKey: string;
}

export interface SoundSettings {
  volume: number;
  reverb: number;
  mode: PlayMode;
  arpStepMs: number;
  timbre: Timbre;
  autoPlay: boolean;
}

export interface RhythmSettings {
  bpm: number;
  patternId: string;
  loop: boolean;
  click: boolean;
  /** Метроном: долей в такте. */
  meter: number;
  accent: boolean;
  /** «Ритм»: задержка звука (колонки + микрофон), мс; null — ещё не подстраивалась. */
  latencyMs: number | null;
  /** «Ритм»: отсеивать щелчки метронома и короткие стуки (шумодав). Выкл — засчитывается любой удар. */
  clickFilter: boolean;
}

export interface ScaleSettings {
  show: boolean;
  rootPc: number;
  scaleId: string;
}

export interface MidiOptions {
  latch: boolean;
  sound: boolean;
  device: string;
  output: string;
  muteInternal: boolean;
}

/** По удару / держите аккорд / по струнам (щипки по одной — точная аппликатура). */
export type ListenMode = 'strum' | 'hold' | 'strings';
/** Чем распознавать: формулы (спектр) или нейросеть Basic Pitch. */
export type ListenEngine = 'dsp' | 'neural';

export interface ListenSettings {
  mode: ListenMode;
  /** Усиление микрофона (×). */
  gain: number;
  /** Сколько держать аккорд в режиме «Держите аккорд», секунды. */
  holdSeconds: number;
  sensitivity: number;
  showOnBoard: boolean;
  /** Автоусиление: программа сама подстраивает громкость микрофона под игру. */
  autoGain: boolean;
  /** Вычитать постоянный шум (гул, вентилятор) — он запоминается, пока гитара молчит. */
  denoise: boolean;
  /** Выбранный микрофон ('' — системный по умолчанию). */
  deviceId: string;
  engine: ListenEngine;
  /** Калибровка под гитару и микрофон (null — не проводилась). */
  calibration: Calibration | null;
}

export interface Settings {
  view: ViewSettings;
  sound: SoundSettings;
  rhythm: RhythmSettings;
  scale: ScaleSettings;
  midi: MidiOptions;
  listen: ListenSettings;
}

export const DEFAULT_TILES: ModuleId[] = ['circle', 'listen', 'sound', 'songbook'];

export const DEFAULT_SETTINGS: Settings = {
  view: {
    theme: 'slavic',
    layout: 'classic',
    tiles: DEFAULT_TILES,
    showNotes: false,
    dotLabel: 'note',
    tuning: 'standard',
    customStrings: [...TUNINGS.standard.strings],
    capo: 0,
    tab: 'songbook',
    circleKey: 'auto',
  },
  sound: { volume: 0.8, reverb: 0.25, mode: 'strum', arpStepMs: 180, timbre: 'steel', autoPlay: true },
  rhythm: { bpm: 90, patternId: 'six', loop: true, click: false, meter: 4, accent: true, latencyMs: null, clickFilter: false },
  scale: { show: false, rootPc: 9, scaleId: 'pentMinor' },
  midi: { latch: true, sound: true, device: 'all', output: '', muteInternal: false },
  listen: {
    mode: 'strum',
    gain: 3,
    holdSeconds: 2.5,
    sensitivity: 0.5,
    showOnBoard: true,
    autoGain: true,
    denoise: true,
    deviceId: '',
    engine: 'dsp',
    calibration: null,
  },
};

/** Аккорд с определённым строем и каподастром: элемент избранного, истории, последовательности. */
export interface ShapeBase {
  tuning: string;
  strings: number[];
  capo: number;
}

export interface SavedShape extends ShapeBase {
  id: string;
  name: string;
  symbol: string;
  nameRu: string;
  board: Board;
  created: number;
}

export interface HistoryEntry extends ShapeBase {
  id: string;
  symbol: string;
  nameRu: string;
  notes: string[];
  time: number;
  source: 'board' | 'midi';
  board?: Board;
  midi?: number[];
}

export interface SeqItem {
  id: string;
  symbol: string;
  board: Board;
  strings: number[];
  capo: number;
  /** Длительность в долях (четвертях). */
  beats: number;
}

/** Песня в песеннике. Текст хранится в формате ChordPro: «[Am]Вот новый [F]поворот». */
export interface Song {
  id: string;
  title: string;
  artist: string;
  body: string;
  capo: number;
  bpm: number;
  /** Сдвиг аккордов песни в полутонах. */
  transpose: number;
  /** Выбранные аппликатуры: символ аккорда → лады. */
  shapes: Record<string, Frets>;
  created: number;
  updated: number;
}

export interface PracticeDay {
  /** Сколько секунд занимались (приложение активно, идёт игра или упражнение). */
  seconds: number;
  /** Аккорды, которые сыграли на гитаре (распознаны микрофоном). */
  chords: string[];
}

export interface Practice {
  days: Record<string, PracticeDay>;
  /** Аккорды, уверенно сыгранные на гитаре хотя бы несколько раз, — «выученные». */
  learned: string[];
  /** Счётчик: сколько раз аккорд был распознан с гитары. */
  heardCount: Record<string, number>;
  lessons: Record<string, { step: number; done: boolean }>;
  /** Лучший результат в «Сменах аккордов» для пары: смен в минуту. */
  changesBest: Record<string, number>;
  /** Лучшая точность в «Ритме», средняя ошибка в мс. */
  rhythmBest: number | null;
}

export const EMPTY_PRACTICE: Practice = { days: {}, learned: [], heardCount: {}, lessons: {}, changesBest: {}, rhythmBest: null };

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

export const todayKey = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
