import type { CollectionsSlice } from './collections';
import type { GuitarSlice } from './guitar';
import type { PracticeSlice } from './practice';
import type { RuntimeSlice } from './runtime';
import type { SettingsSlice } from './settings';
import type { SongbookSlice } from './songbook';

/** Всё состояние приложения — одно хранилище, собранное из срезов. */
export type AppState = SettingsSlice & GuitarSlice & CollectionsSlice & SongbookSlice & PracticeSlice & RuntimeSlice;

export type SetState = (partial: Partial<AppState> | ((s: AppState) => Partial<AppState>)) => void;
export type GetState = () => AppState;
export type Slice<T> = (set: SetState, get: GetState) => T;
