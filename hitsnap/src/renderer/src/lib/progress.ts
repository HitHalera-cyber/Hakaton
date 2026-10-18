import { formatNumber } from './format'
import { answerKind, MODE_INFO, YEAR_WIN_DISTANCE, type GameConfig, type Round } from './game'
import { todayKey } from './random'

// Player progression: levels from points earned, the daily-challenge streak
// and a shareable result line.

const TITLES = [
  'Новичок',
  'Слушатель',
  'Любитель',
  'Меломан',
  'Знаток',
  'Эксперт',
  'Диджей',
  'Продюсер',
  'Маэстро',
  'Легенда'
]

/** Points needed to reach `level` (level 1 needs nothing). */
export function pointsForLevel(level: number): number {
  return 1500 * (level - 1) * level
}

export interface Level {
  level: number
  title: string
  /** Progress to the next level, 0..1. */
  progress: number
  toNext: number
}

export function levelFor(points: number): Level {
  let level = 1
  while (points >= pointsForLevel(level + 1)) level++
  const from = pointsForLevel(level)
  const to = pointsForLevel(level + 1)
  return {
    level,
    title: TITLES[Math.min(TITLES.length - 1, Math.floor((level - 1) / 2))],
    progress: (points - from) / (to - from),
    toNext: to - points
  }
}

/** Days in a row with a finished «Песня дня», counting back from today (or yesterday). */
export function dailyStreak(days: string[], today = new Date()): number {
  const done = new Set(days)
  const d = new Date(today)
  if (!done.has(todayKey(d))) d.setDate(d.getDate() - 1)
  let streak = 0
  while (done.has(todayKey(d))) {
    streak++
    d.setDate(d.getDate() - 1)
  }
  return streak
}

function roundEmoji(r: Round, kind: ReturnType<typeof answerKind>): string {
  if (kind === 'year') {
    const d = r.yearGuess === undefined ? Infinity : Math.abs(r.yearGuess - r.song.year)
    return d === 0 ? '🎯' : d <= YEAR_WIN_DISTANCE ? '🟩' : d <= 5 ? '🟨' : '⬛'
  }
  if (r.status !== 'won') return '⬛'
  return ['🟩', '🟨', '🟧'][r.stage] ?? '🟧'
}

/** "HitSnap · Классика · 7/10 · 6 850 очков" + a row of squares, like Wordle. */
export function shareText(config: GameConfig, rounds: Round[], score: number): string {
  const kind = answerKind(config.mode)
  const done = rounds.filter((r) => r.status !== 'playing')
  const correct = done.filter((r) => r.status === 'won').length
  const title = [
    'HitSnap',
    config.source?.label ?? MODE_INFO[config.mode].title,
    config.dailyKey ? config.dailyKey.split('-').reverse().join('.') : null,
    `${correct}/${done.length}`,
    config.mode === 'practice' || config.mode === 'party' ? null : `${formatNumber(score)} очков`
  ]
    .filter(Boolean)
    .join(' · ')
  const squares = done.map((r) => roundEmoji(r, kind)).join('')
  return `${title}\n${squares}`
}
