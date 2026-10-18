import type { Genre, Lang, Song } from '@shared/types'
import { createRng, hashString, shuffle, type Rng } from './random'

// Pure game rules: modes, stages, scoring and how songs are picked.

export type GameMode = 'classic' | 'survival' | 'daily' | 'practice'
export type Difficulty = 'easy' | 'normal' | 'hard'

/** How many seconds of the song each stage plays. */
export const STAGES: Record<Difficulty, number[]> = {
  easy: [2, 5, 10],
  normal: [1, 3, 5],
  hard: [0.5, 1, 3]
}

export const BASE_POINTS = [1000, 500, 250]
export const HINT_PENALTY = 0.2
export const MAX_HINTS = 2
export const SURVIVAL_LIVES = 3
export const DAILY_ROUNDS = 5

export interface Filters {
  decades: number[] // 1960, 1970, …; empty = all
  genres: Genre[]
  langs: Lang[]
}

export const EMPTY_FILTERS: Filters = { decades: [], genres: [], langs: [] }

export interface GameConfig {
  mode: GameMode
  difficulty: Difficulty
  rounds: number // Infinity for survival / practice
  filters: Filters
  seed: number
  dailyKey?: string
}

export interface Guess {
  songId: string
  label: string
  stage: number
  sameArtist: boolean
  skipped?: boolean
}

export type RoundStatus = 'playing' | 'won' | 'lost'

export interface Round {
  song: Song
  offset: number
  stage: number
  guesses: Guess[]
  hints: number
  status: RoundStatus
  points: number
  startedAt: number
  endedAt?: number
  coverUrl?: string
  link?: string
  album?: string
}

/** Decade bucket; everything before the 60s counts as the 60s. */
export function decadeOf(year: number): number {
  return Math.max(1960, Math.floor(year / 10) * 10)
}

export function matchesFilters(song: Song, f: Filters): boolean {
  if (f.decades.length && !f.decades.includes(decadeOf(song.year))) return false
  if (f.genres.length && !f.genres.includes(song.genre)) return false
  if (f.langs.length && !f.langs.includes(song.lang)) return false
  return true
}

export function streakMultiplier(streak: number): number {
  return 1 + Math.min(streak, 5) * 0.1
}

export function pointsFor(stage: number, streakBefore: number, hints: number): number {
  const base = BASE_POINTS[stage] ?? 0
  return Math.round((base * streakMultiplier(streakBefore) * (1 - HINT_PENALTY * hints)) / 10) * 10
}

/** Same artist (ignoring "feat." and "&" partners) — worth telling the player. */
export function sameArtist(a: Song, b: Song): boolean {
  const main = (s: Song): string[] =>
    s.artist
      .toLowerCase()
      .split(/\s*(?:&|,|feat\.?| x | и )\s*/)
      .map((p) => p.replace(/^the\s+/, '').trim())
      .filter(Boolean)
  const pa = main(a)
  return main(b).some((p) => pa.includes(p))
}

export function isCorrect(answer: Song, guess: Song): boolean {
  if (answer.id === guess.id) return true
  const n = (s: string): string => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '')
  return n(answer.title) === n(guess.title) && sameArtist(answer, guess)
}

/**
 * Order in which songs will be asked. Recently heard songs go to the back so
 * a session rarely repeats; the daily challenge ignores filters and history.
 */
export function buildQueue(pool: Song[], config: GameConfig, recentIds: string[] = []): Song[] {
  const rng = createRng(config.seed)
  if (config.mode === 'daily') {
    const stable = [...pool].sort((a, b) => a.id.localeCompare(b.id))
    return shuffle(stable, rng)
  }
  const filtered = pool.filter((s) => matchesFilters(s, config.filters))
  const recent = new Set(recentIds)
  const fresh = filtered.filter((s) => !recent.has(s.id))
  const stale = filtered.filter((s) => recent.has(s.id))
  return [...shuffle(fresh, rng), ...shuffle(stale, rng)]
}

/** Where in the preview the clip starts — away from the very edges. */
export function pickOffset(duration: number, longestStage: number, rng: Rng): number {
  const max = Math.max(0, duration - longestStage - 1)
  const min = Math.min(2, max)
  return min + rng() * (max - min)
}

export function seedFor(mode: GameMode, dailyKey?: string): number {
  return mode === 'daily' && dailyKey ? hashString(`hitsnap-daily-${dailyKey}`) : (Math.random() * 2 ** 32) >>> 0
}

export interface Hint {
  label: string
  value: string
}

export function hintsFor(song: Song): Hint[] {
  return [
    { label: 'Год выпуска', value: String(song.year) },
    { label: 'Исполнитель начинается на', value: `«${song.artist.trim()[0]?.toUpperCase() ?? '?'}…»` }
  ]
}

export const MODE_INFO: Record<GameMode, { title: string; subtitle: string }> = {
  classic: { title: 'Классика', subtitle: 'Серия раундов, очки за скорость' },
  survival: { title: 'Выживание', subtitle: '3 жизни — играем, пока не кончатся' },
  daily: { title: 'Песня дня', subtitle: '5 песен, одинаковых для всех сегодня' },
  practice: { title: 'Тренировка', subtitle: 'Без очков и без спешки' }
}

export const GENRE_LABELS: Record<Genre, string> = {
  pop: 'Поп',
  rock: 'Рок',
  hiphop: 'Хип-хоп',
  electronic: 'Электроника',
  rnb: 'R&B / соул',
  metal: 'Метал',
  indie: 'Инди',
  disco: 'Диско',
  'russian-pop': 'Русская эстрада',
  'russian-rock': 'Русский рок',
  'russian-rap': 'Русский рэп'
}

export const LANG_LABELS: Record<Lang, string> = { en: 'На английском', ru: 'На русском', other: 'Другие языки' }
