import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { SoundEffect } from '@/lib/audio'
import { EMPTY_FILTERS, PLAYER_COLORS, type BotLevel, type ClipStart, type Difficulty, type Filters, type GameMode, type Player } from '@/lib/game'
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
  clipStart: ClipStart
  /** Last mode picked for a collection in «Как играть?». */
  stationMode: GameMode
  botLevel: BotLevel
  /** Shown in the sidebar and as the first party player. */
  profileName: string
  profileEmoji: string
  players: Player[]
  partyRounds: number
  /** Sound effect applied to clips in regular games. */
  effect: SoundEffect
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
  filters: EMPTY_FILTERS,
  clipStart: 'random',
  stationMode: 'classic',
  botLevel: 'mid',
  profileName: '',
  profileEmoji: '🎧',
  players: [
    { name: 'Игрок 1', color: PLAYER_COLORS[0] },
    { name: 'Игрок 2', color: PLAYER_COLORS[1] }
  ],
  partyRounds: 10,
  effect: 'none'
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
