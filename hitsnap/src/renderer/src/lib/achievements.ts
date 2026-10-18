import type { GameMode, Round } from './game'
import { decadeOf } from './game'

// Achievements are derived from stats after each round / game.

export interface AchievementContext {
  totals: { wins: number; rounds: number; games: number; firstStage: number }
  bestStreak: number
  langsWon: string[]
  decadeWins: Record<string, number>
  dailyDone: number
  game?: { mode: GameMode; rounds: Round[]; score: number }
}

export interface Achievement {
  id: string
  title: string
  description: string
  icon: string
  test: (c: AchievementContext) => boolean
}

const won = (r: Round): boolean => r.status === 'won'

export const ACHIEVEMENTS: Achievement[] = [
  { id: 'first-win', icon: '🎵', title: 'Первая нота', description: 'Угадать первую песню', test: (c) => c.totals.wins >= 1 },
  { id: 'perfect-pitch', icon: '⚡', title: 'Абсолютный слух', description: 'Угадать песню с самой первой попытки', test: (c) => c.totals.firstStage >= 1 },
  { id: 'lightning-10', icon: '🌩️', title: 'Молния', description: '10 песен с первой попытки', test: (c) => c.totals.firstStage >= 10 },
  { id: 'streak-5', icon: '🔥', title: 'В ударе', description: 'Серия из 5 угаданных подряд', test: (c) => c.bestStreak >= 5 },
  { id: 'streak-10', icon: '☄️', title: 'Неостановимый', description: 'Серия из 10 угаданных подряд', test: (c) => c.bestStreak >= 10 },
  { id: 'hundred', icon: '💯', title: 'Сотня', description: 'Всего угадано 100 песен', test: (c) => c.totals.wins >= 100 },
  { id: 'polyglot', icon: '🌍', title: 'Полиглот', description: 'Угадать песни на русском, английском и других языках', test: (c) => ['ru', 'en', 'other'].every((l) => c.langsWon.includes(l)) },
  { id: 'eighties', icon: '📼', title: 'Дитя 80-х', description: 'Угадать 10 песен 80-х', test: (c) => (c.decadeWins['1980'] ?? 0) >= 10 },
  { id: 'nineties', icon: '💿', title: 'Лихие 90-е', description: 'Угадать 10 песен 90-х', test: (c) => (c.decadeWins['1990'] ?? 0) >= 10 },
  { id: 'daily', icon: '📅', title: 'Ритуал', description: 'Пройти «Песню дня»', test: (c) => c.dailyDone >= 1 },
  { id: 'daily-7', icon: '🗓️', title: 'Неделя музыки', description: 'Пройти «Песню дня» 7 раз', test: (c) => c.dailyDone >= 7 },
  {
    id: 'flawless',
    icon: '👑',
    title: 'Без единой ошибки',
    description: 'Пройти классическую игру, угадав все песни',
    test: (c) => !!c.game && c.game.mode === 'classic' && c.game.rounds.length >= 5 && c.game.rounds.every(won)
  },
  {
    id: 'no-hints',
    icon: '🧠',
    title: 'Своим умом',
    description: 'Угадать 5+ песен за игру без подсказок',
    test: (c) => !!c.game && c.game.rounds.filter(won).length >= 5 && c.game.rounds.every((r) => r.hints === 0)
  },
  { id: 'survivor', icon: '🛡️', title: 'Выживший', description: 'Угадать 15 песен в режиме «Выживание»', test: (c) => !!c.game && c.game.mode === 'survival' && c.game.rounds.filter(won).length >= 15 },
  { id: 'score-8000', icon: '🏆', title: 'Рекордсмен', description: 'Набрать 8000 очков за игру', test: (c) => !!c.game && c.game.score >= 8000 }
]

export function wonDecade(r: Round): string {
  return String(decadeOf(r.song.year))
}
