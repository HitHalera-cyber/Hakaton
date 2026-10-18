import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { EMPTY_FILTERS, type Difficulty, type Filters } from '@/lib/game'
import { diskStorage } from './persist'

export type ThemePref = 'system' | 'light' | 'dark'
export type Accent = 'violet' | 'ocean' | 'sunset' | 'lime' | 'rose'

export interface Settings {
  theme: ThemePref
  accent: Accent
  volume: number
  difficulty: Difficulty
  roundsPerGame: number
  autoplay: boolean
  sfx: boolean
  visualizer: boolean
  filters: Filters
}

interface SettingsStore extends Settings {
  update: (patch: Partial<Settings>) => void
}

export const DEFAULT_SETTINGS: Settings = {
  theme: 'system',
  accent: 'violet',
  volume: 0.8,
  difficulty: 'normal',
  roundsPerGame: 10,
  autoplay: true,
  sfx: true,
  visualizer: true,
  filters: EMPTY_FILTERS
}

export const useSettings = create<SettingsStore>()(
  persist(
    (set) => ({
      ...DEFAULT_SETTINGS,
      update: (patch) => set(patch)
    }),
    { name: 'settings', storage: diskStorage, version: 1 }
  )
)
