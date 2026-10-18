import type { Genre, Lang, Song, Tier } from '@shared/types'
import { createRng, hashString, shuffle, type Rng } from './random'

// Pure game rules: modes, stages, scoring and how songs are picked.

export type GameMode = 'classic' | 'survival' | 'daily' | 'practice' | 'quiz' | 'year' | 'party'
export type Difficulty = 'easy' | 'normal' | 'hard'
/** How the player answers: find the song in search, pick one of four, or name the year. */
export type AnswerKind = 'search' | 'choice' | 'year'
export type Popularity = 'hits' | 'popular' | 'all' | 'rare'
/** Where in the audio the clip starts. */
export type ClipStart = 'random' | 'intro'

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
export const QUIZ_OPTIONS = 4
/** Picking from four answers is easier than searching, so it pays less. */
export const QUIZ_FACTOR = 0.5
export const YEAR_RANGE = { min: 1950, max: new Date().getFullYear() }

export const PLAYER_COLORS = ['#8b5cf6', '#f97316', '#0ea5e9', '#16a34a']

export interface Player {
  name: string
  color: string
}

export interface Filters {
  decades: number[] // 1960, 1970, …; empty = all
  genres: Genre[]
  langs: Lang[]
  popularity?: Popularity
}

export const EMPTY_FILTERS: Filters = { decades: [], genres: [], langs: [], popularity: 'all' }

/** What the game is drawn from, when it is not the whole base (a genre station, a playlist…). */
export interface GameSource {
  label: string
  icon?: string
}

export interface GameConfig {
  mode: GameMode
  difficulty: Difficulty
  rounds: number // Infinity for survival / practice
  filters: Filters
  seed: number
  clipStart: ClipStart
  dailyKey?: string
  source?: GameSource
  players?: Player[]
}

export interface Guess {
  songId: string
  label: string
  stage: number
  sameArtist: boolean
  skipped?: boolean
  /** Party: who answered. */
  player?: number
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
  /** Quiz: the four answers on offer. */
  options?: Song[]
  /** Year mode: the player's answer. */
  yearGuess?: number
  /** Party: who guessed it. */
  winner?: number
}

export function answerKind(mode: GameMode): AnswerKind {
  return mode === 'quiz' ? 'choice' : mode === 'year' ? 'year' : 'search'
}

/** Decade bucket; everything before the 60s counts as the 60s. */
export function decadeOf(year: number): number {
  return Math.max(1960, Math.floor(year / 10) * 10)
}

export function matchesPopularity(song: Song, popularity: Popularity = 'all'): boolean {
  const tier = song.tier ?? 2
  if (popularity === 'hits') return tier === 1
  if (popularity === 'popular') return tier <= 2
  if (popularity === 'rare') return tier === 3
  return true
}

export function matchesFilters(song: Song, f: Filters): boolean {
  if (f.decades.length && !f.decades.includes(decadeOf(song.year))) return false
  if (f.genres.length && !f.genres.includes(song.genre)) return false
  if (f.langs.length && !f.langs.includes(song.lang)) return false
  return matchesPopularity(song, f.popularity)
}

export function streakMultiplier(streak: number): number {
  return 1 + Math.min(streak, 5) * 0.1
}

export function pointsFor(stage: number, streakBefore: number, hints: number, factor = 1): number {
  const base = BASE_POINTS[stage] ?? 0
  return Math.round((base * factor * streakMultiplier(streakBefore) * (1 - HINT_PENALTY * hints)) / 10) * 10
}

/** Year mode: how close the answer is, 0..1. A year off is still very good. */
export function yearCloseness(guess: number, actual: number): number {
  const d = Math.abs(guess - actual)
  if (d === 0) return 1
  if (d === 1) return 0.8
  if (d <= 2) return 0.6
  if (d <= 4) return 0.35
  if (d <= 7) return 0.15
  return 0
}

/** Within two years counts as a correct answer. */
export const YEAR_WIN_DISTANCE = 2

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
    const stable = [...pool].filter((s) => s.tier <= 2).sort((a, b) => a.id.localeCompare(b.id))
    return shuffle(stable, rng)
  }
  let filtered = pool.filter((s) => matchesFilters(s, config.filters))
  if (config.mode === 'year') filtered = filtered.filter((s) => s.year >= 1900 && !s.filePath)
  const recent = new Set(recentIds)
  const fresh = filtered.filter((s) => !recent.has(s.id))
  const stale = filtered.filter((s) => recent.has(s.id))
  return [...shuffle(fresh, rng), ...shuffle(stale, rng)]
}

/**
 * Three wrong answers for the quiz. Similar songs (same genre, close years)
 * make it a real question rather than an obvious one.
 */
export function quizOptions(answer: Song, pool: Song[], rng: Rng): Song[] {
  const others = pool.filter((s) => s.id !== answer.id && !sameArtist(s, answer) && s.title !== answer.title)
  const close = others.filter((s) => s.genre === answer.genre && Math.abs(s.year - answer.year) <= 12)
  const sameGenre = others.filter((s) => s.genre === answer.genre)
  const picks: Song[] = []
  const usedArtists = new Set<string>()
  for (const source of [close, sameGenre, others]) {
    for (const s of shuffle(source, rng)) {
      if (picks.length >= QUIZ_OPTIONS - 1) break
      const key = s.artist.toLowerCase()
      if (usedArtists.has(key) || picks.some((p) => p.id === s.id)) continue
      usedArtists.add(key)
      picks.push(s)
    }
  }
  return shuffle([answer, ...picks], rng)
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

export function hintsFor(song: Song, kind: AnswerKind = 'search'): Hint[] {
  if (kind === 'year') {
    return [
      { label: 'Десятилетие', value: `${decadeOf(song.year)}-е` },
      { label: 'Исполнитель', value: song.artist }
    ]
  }
  return [
    { label: 'Год выпуска', value: String(song.year) },
    { label: 'Исполнитель начинается на', value: `«${song.artist.trim()[0]?.toUpperCase() ?? '?'}…»` }
  ]
}

export const MODE_INFO: Record<GameMode, { title: string; subtitle: string }> = {
  classic: { title: 'Классика', subtitle: 'Серия раундов, очки за скорость' },
  survival: { title: 'Выживание', subtitle: '3 жизни — играем, пока не кончатся' },
  daily: { title: 'Песня дня', subtitle: '5 песен, одинаковых для всех сегодня' },
  quiz: { title: 'Викторина', subtitle: 'Четыре варианта ответа — выберите верный' },
  year: { title: 'Угадай год', subtitle: 'Слушайте и называйте год выхода песни' },
  party: { title: 'Вечеринка', subtitle: '2–4 игрока, кто первым нажмёт — тот отвечает' },
  practice: { title: 'Тренировка', subtitle: 'Без очков и без спешки' }
}

export const GENRE_LABELS: Record<Genre, string> = {
  pop: 'Поп',
  rock: 'Рок',
  metal: 'Метал',
  indie: 'Инди',
  electronic: 'Электроника',
  disco: 'Диско',
  hiphop: 'Хип-хоп',
  rnb: 'R&B и соул',
  jazz: 'Джаз и блюз',
  country: 'Кантри',
  latin: 'Латино',
  kpop: 'K-pop и J-pop',
  soundtrack: 'Кино и игры',
  'russian-pop': 'Русская эстрада',
  'russian-rock': 'Русский рок',
  'russian-rap': 'Русский рэп',
  soviet: 'Советская эстрада'
}

/** Look of a genre station card. */
export const GENRE_STYLE: Record<Genre, { emoji: string; from: string; to: string }> = {
  pop: { emoji: '🎤', from: '#ec4899', to: '#8b5cf6' },
  rock: { emoji: '🎸', from: '#ef4444', to: '#7c2d12' },
  metal: { emoji: '🤘', from: '#52525b', to: '#18181b' },
  indie: { emoji: '🌙', from: '#14b8a6', to: '#4338ca' },
  electronic: { emoji: '🎛️', from: '#06b6d4', to: '#7c3aed' },
  disco: { emoji: '🪩', from: '#f59e0b', to: '#db2777' },
  hiphop: { emoji: '🎧', from: '#f97316', to: '#1f2937' },
  rnb: { emoji: '💜', from: '#a855f7', to: '#be185d' },
  jazz: { emoji: '🎷', from: '#b45309', to: '#1e3a8a' },
  country: { emoji: '🤠', from: '#d97706', to: '#65a30d' },
  latin: { emoji: '💃', from: '#f43f5e', to: '#f59e0b' },
  kpop: { emoji: '✨', from: '#f472b6', to: '#38bdf8' },
  soundtrack: { emoji: '🎬', from: '#334155', to: '#0ea5e9' },
  'russian-pop': { emoji: '🌟', from: '#e11d48', to: '#2563eb' },
  'russian-rock': { emoji: '⚡', from: '#991b1b', to: '#111827' },
  'russian-rap': { emoji: '🔥', from: '#ea580c', to: '#4c1d95' },
  soviet: { emoji: '📻', from: '#b91c1c', to: '#ca8a04' }
}

export const LANG_LABELS: Record<Lang, string> = { en: 'На английском', ru: 'На русском', other: 'Другие языки' }

export const POPULARITY_INFO: Record<Popularity, { label: string; hint: string }> = {
  hits: { label: 'Только хиты', hint: 'Песни, которые знают все' },
  popular: { label: 'Популярное', hint: 'Хиты и известные песни' },
  all: { label: 'Всё подряд', hint: 'Вся база, от хитов до редкостей' },
  rare: { label: 'Для знатоков', hint: 'Малоизвестные песни и редкости' }
}
