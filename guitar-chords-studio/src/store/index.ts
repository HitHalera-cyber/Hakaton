// Единое хранилище приложения (Zustand). Сохраняемая часть пишется в localStorage с номером версии схемы.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useShallow } from 'zustand/react/shallow';
import { isModuleId } from '../modules/ids';
import { createCollectionsSlice } from './collections';
import { createGuitarSlice, modelOf } from './guitar';
import { DEFAULT_SETTINGS, DEFAULT_TILES, EMPTY_PRACTICE, type Settings } from './model';
import { createPracticeSlice } from './practice';
import { createRuntimeSlice } from './runtime';
import { createSettingsSlice } from './settings';
import { createSongbookSlice } from './songbook';
import type { AppState } from './types';

export type { AppState } from './types';

const PERSISTED = ['settings', 'board', 'saved', 'history', 'sequence', 'songs', 'currentSongId', 'practice', 'windows'] as const;

/** Сохранённые настройки дополняются полями, появившимися в новых версиях. */
function mergeSettings(saved: Partial<Settings> | undefined): Settings {
  const s = saved ?? {};
  const merged = Object.fromEntries(
    (Object.keys(DEFAULT_SETTINGS) as (keyof Settings)[]).map((k) => [k, { ...DEFAULT_SETTINGS[k], ...(s[k] ?? {}) }]),
  ) as unknown as Settings;
  if (!isModuleId(merged.view.tab)) merged.view.tab = DEFAULT_SETTINGS.view.tab;
  if (!Array.isArray(merged.view.tiles) || merged.view.tiles.length !== 4 || !merged.view.tiles.every(isModuleId))
    merged.view.tiles = DEFAULT_TILES;
  return merged;
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...createSettingsSlice(set, get),
      ...createGuitarSlice(set, get),
      ...createCollectionsSlice(set, get),
      ...createSongbookSlice(set, get),
      ...createPracticeSlice(set, get),
      ...createRuntimeSlice(set, get),
    }),
    {
      name: 'gcs.state',
      version: 1,
      partialize: (s) => Object.fromEntries(PERSISTED.map((k) => [k, s[k]])) as Partial<AppState>,
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<AppState>;
        return {
          ...current,
          ...p,
          settings: mergeSettings(p.settings),
          practice: { ...EMPTY_PRACTICE, ...(p.practice ?? {}) },
          songs: p.songs?.length ? p.songs : current.songs,
        };
      },
    },
  ),
);

export const store = useStore;

/** Выбрать несколько полей хранилища (перерисовка — только при их изменении). */
export const usePick = <T>(fn: (s: AppState) => T) => useStore(useShallow(fn));

/** Производные данные инструмента для компонентов. */
export const useGuitar = () => useStore((s) => modelOf(s));
