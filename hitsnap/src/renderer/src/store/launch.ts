import { CATALOG } from '@shared/catalog'
import type { SoundEffect } from '@/lib/audio'
import type { Song } from '@shared/types'
import { DAILY_ROUNDS, EMPTY_FILTERS, seedFor, type Filters, type GameMode, type GameSource } from '@/lib/game'
import { todayKey } from '@/lib/random'
import { WEEKLY_ROUNDS, weeklyChallenge } from '@/lib/weekly'
import { useGame } from './game'
import { allSongs, useLibrary } from './library'
import { useSettings } from './settings'
import { useUi } from './ui'

export interface LaunchOptions {
  /** Songs to draw from; the whole base when omitted. */
  pool?: Song[]
  /** Filters for this game; the ones on the home screen when omitted. */
  filters?: Filters
  source?: GameSource
  /** Overrides the sound effect from the settings (the roulette picks its own). */
  effect?: SoundEffect
}

/** Starts a game of `mode` with the player's settings. */
export function launch(mode: GameMode, opts: LaunchOptions = {}): void {
  const s = useSettings.getState()
  const lib = useLibrary.getState()
  const today = todayKey()
  const rounds =
    mode === 'daily'
      ? DAILY_ROUNDS
      : mode === 'party'
        ? s.partyRounds
        : mode === 'survival' || mode === 'practice' || mode === 'blitz'
          ? Infinity
          : s.roundsPerGame
  const pool = opts.pool ?? (mode === 'daily' ? CATALOG : allSongs(lib.custom, lib.packs, lib.localSongs))
  if (!pool.length) {
    useUi.getState().toast({ title: 'Здесь пока нет песен', tone: 'error', icon: '🎵' })
    return
  }
  void useGame.getState().start(
    {
      mode,
      difficulty: s.difficulty,
      rounds,
      filters: mode === 'daily' ? EMPTY_FILTERS : (opts.filters ?? s.filters),
      seed: seedFor(mode, today),
      clipStart: mode === 'daily' ? 'random' : s.clipStart,
      dailyKey: mode === 'daily' ? today : undefined,
      source: opts.source,
      players: mode === 'party' ? s.players : undefined,
      effect: mode === 'daily' ? 'none' : (opts.effect ?? s.effect),
      bot: mode === 'duel' ? s.botLevel : undefined
    },
    pool
  )
}

/** Same game again with a fresh shuffle. */
export function replay(): void {
  const { config, pool } = useGame.getState()
  if (!config) return
  void useGame.getState().start({ ...config, seed: config.weekKey ? config.seed : seedFor(config.mode, config.dailyKey) }, pool)
}

/** «Испытание недели»: this week's ten songs, the same for everyone. */
export function launchWeekly(): void {
  const { key, theme, seed } = weeklyChallenge()
  void useGame.getState().start(
    {
      mode: 'classic',
      difficulty: 'normal',
      rounds: WEEKLY_ROUNDS,
      filters: { ...EMPTY_FILTERS, ...theme.filters, popularity: 'popular' },
      seed,
      clipStart: 'random',
      weekKey: key,
      source: { label: `Испытание недели · ${theme.title}`, icon: theme.emoji },
      effect: 'none'
    },
    CATALOG
  )
}
