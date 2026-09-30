// Настройки: вид, звук, ритм, гамма, MIDI, прослушивание.

import { DEFAULT_SETTINGS, type Settings } from './model';
import type { Slice } from './types';

export interface SettingsSlice {
  settings: Settings;
  patchView: (p: Partial<Settings['view']>) => void;
  patchSound: (p: Partial<Settings['sound']>) => void;
  patchRhythm: (p: Partial<Settings['rhythm']>) => void;
  patchScale: (p: Partial<Settings['scale']>) => void;
  patchMidi: (p: Partial<Settings['midi']>) => void;
  patchListen: (p: Partial<Settings['listen']>) => void;
}

export const createSettingsSlice: Slice<SettingsSlice> = (set) => {
  const patch =
    <K extends keyof Settings>(key: K) =>
    (p: Partial<Settings[K]>) =>
      set((s) => ({ settings: { ...s.settings, [key]: { ...s.settings[key], ...p } } }));
  return {
    settings: DEFAULT_SETTINGS,
    patchView: patch('view'),
    patchSound: patch('sound'),
    patchRhythm: patch('rhythm'),
    patchScale: patch('scale'),
    patchMidi: patch('midi'),
    patchListen: patch('listen'),
  };
};
