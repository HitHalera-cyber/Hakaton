// Сохраняемые настройки приложения: значения по умолчанию и совместимость со старыми версиями.

import { useEffect } from 'react';
import type { DotLabel } from '../features/fretboard/Fretboard';
import type { ScaleSettings } from '../features/scales/ScalesPanel';
import type { SoundSettings } from '../features/sound/SoundPanel';
import { DEFAULT_RHYTHM, type RhythmSettings } from '../features/sequencer/useSequencer';
import { TIMBRE_NAMES } from '../core/audio/engine';
import { TUNINGS } from '../core/music/tunings';
import { isTab, type TabId } from './navigation';
import { DEFAULT_THEME, migrateTheme, type ThemeId } from './themes';
import { useStored } from './useStored';

export interface ViewSettings {
  theme: ThemeId;
  showNotes: boolean;
  dotLabel: DotLabel;
  tuning: string;
  customStrings: number[];
  capo: number;
  tab: TabId;
  /** Тональность для квинтового круга: 'auto' или «позиция-лад». */
  circleKey: string;
}

export const DEFAULT_VIEW: ViewSettings = {
  theme: DEFAULT_THEME,
  showNotes: false,
  dotLabel: 'note',
  tuning: 'standard',
  customStrings: [...TUNINGS.standard.strings],
  capo: 0,
  tab: 'sound',
  circleKey: 'auto',
};

export const DEFAULT_SOUND: SoundSettings = { volume: 0.8, reverb: 0.25, mode: 'strum', arpStepMs: 180, timbre: 'steel', autoPlay: true };
export const DEFAULT_SCALE: ScaleSettings = { show: false, rootPc: 9, scaleId: 'pentMinor' };

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

/** Записи из версии 1.0 не знали о строе и каподастре — дополняем. */
export function normalizeShape<T extends { tuning?: string; strings?: number[]; capo?: number }>(
  x: T,
): T & { strings: number[]; capo: number; tuning: string } {
  const tuning = x.tuning && TUNINGS[x.tuning] ? x.tuning : 'standard';
  return { ...x, tuning, strings: x.strings ?? TUNINGS[tuning].strings, capo: x.capo ?? 0 };
}

export function useSettings() {
  const [view, setView] = useStored<ViewSettings>('gc.view', DEFAULT_VIEW);
  const [sound, setSound] = useStored<SoundSettings>('gc.sound', DEFAULT_SOUND);
  const [rhythm, setRhythm] = useStored<RhythmSettings>('gc.rhythm', DEFAULT_RHYTHM);
  const [scale, setScale] = useStored<ScaleSettings>('gc.scale', DEFAULT_SCALE);

  // Совместимость с настройками прошлых версий.
  useEffect(() => {
    setView((v) => ({
      ...v,
      theme: migrateTheme(v.theme),
      tab: isTab(v.tab) ? v.tab : 'sound',
      tuning: TUNINGS[v.tuning] ? v.tuning : 'standard',
      circleKey: v.circleKey ?? 'auto',
    }));
    if (!(sound.timbre in TIMBRE_NAMES)) setSound((s) => ({ ...s, timbre: 'steel' }));
  }, []);

  return {
    view,
    patchView: (p: Partial<ViewSettings>) => setView((v) => ({ ...v, ...p })),
    sound,
    patchSound: (p: Partial<SoundSettings>) => setSound((s) => ({ ...s, ...p })),
    rhythm,
    patchRhythm: (p: Partial<RhythmSettings>) => setRhythm((r) => ({ ...r, ...p })),
    scale,
    patchScale: (p: Partial<ScaleSettings>) => setScale((s) => ({ ...s, ...p })),
  };
}

export type Settings = ReturnType<typeof useSettings>;
