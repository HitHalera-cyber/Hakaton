import type { SoundEffect } from './audio'
import type { GameMode, Round } from './game'
import type { ArcadeGame } from './quests'
import { decadeOf, pointsFor } from './game'

// Achievements are derived from stats after each round / game.

export interface AchievementContext {
  totals: { wins: number; rounds: number; games: number; firstStage: number }
  bestStreak: number
  langsWon: string[]
  decadeWins: Record<string, number>
  dailyDone: number
  level: number
  arcade: Partial<Record<ArcadeGame, number>>
  questsTotal: number
  effectWins: Partial<Record<SoundEffect, number>>
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
const botPoints = (rounds: Round[]): number => rounds.reduce((sum, r) => sum + (r.botStage != null ? pointsFor(r.botStage, 0, 0) : 0), 0)

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
  { id: 'score-8000', icon: '🏆', title: 'Рекордсмен', description: 'Набрать 8000 очков за игру', test: (c) => !!c.game && c.game.score >= 8000 },
  {
    id: 'quiz-master',
    icon: '🧩',
    title: 'Эрудит',
    description: 'Ответить верно на все вопросы викторины (от 5 раундов)',
    test: (c) => !!c.game && c.game.mode === 'quiz' && c.game.rounds.length >= 5 && c.game.rounds.every(won)
  },
  {
    id: 'year-sniper',
    icon: '🎯',
    title: 'Машина времени',
    description: 'Назвать год песни точно',
    test: (c) => !!c.game && c.game.rounds.some((r) => r.yearGuess !== undefined && r.yearGuess === r.song.year)
  },
  {
    id: 'party',
    icon: '🎉',
    title: 'Душа компании',
    description: 'Сыграть «Вечеринку» с друзьями',
    test: (c) => !!c.game && c.game.mode === 'party' && c.game.rounds.length >= 3
  },
  {
    id: 'rare-ear',
    icon: '💎',
    title: 'Слух на редкости',
    description: 'Угадать малоизвестную песню с первой попытки',
    test: (c) => !!c.game && c.game.rounds.some((r) => won(r) && r.stage === 0 && r.song.tier === 3)
  },
  { id: 'level-10', icon: '🚀', title: 'Десятый уровень', description: 'Дойти до 10-го уровня', test: (c) => c.level >= 10 },
  {
    id: 'blitz-10',
    icon: '⏱️',
    title: 'Скорострел',
    description: 'Угадать 10 песен за один «Блиц»',
    test: (c) => !!c.game && c.game.mode === 'blitz' && c.game.rounds.filter(won).length >= 10
  },
  {
    id: 'artist-8',
    icon: '🎙️',
    title: 'Узнаю по голосу',
    description: 'Назвать 8 исполнителей за игру в «Кто поёт?»',
    test: (c) => !!c.game && c.game.mode === 'artist' && c.game.rounds.filter(won).length >= 8
  },
  {
    id: 'duel-win',
    icon: '🤖',
    title: 'Человек сильнее машины',
    description: 'Обыграть бота в «Дуэли» (от 5 раундов)',
    test: (c) => !!c.game && c.game.mode === 'duel' && c.game.rounds.length >= 5 && c.game.score > botPoints(c.game.rounds)
  },
  { id: 'reverse', icon: '🔄', title: 'Ухо наизнанку', description: 'Угадать песню, звучащую задом наперёд', test: (c) => (c.effectWins.reverse ?? 0) >= 1 },
  {
    id: 'effects-all',
    icon: '🎛️',
    title: 'Звукорежиссёр',
    description: 'Угадать песню с каждым звуковым эффектом',
    test: (c) => (['reverse', 'fast', 'slow', 'muffled', 'phone', 'bass'] as const).every((e) => (c.effectWins[e] ?? 0) > 0)
  },
  {
    id: 'arcade-all',
    icon: '🕹️',
    title: 'Завсегдатай Игротеки',
    description: 'Сыграть во все мини-игры',
    test: (c) => (['older', 'timeline', 'whose', 'odd'] as const).every((g) => c.arcade[g] !== undefined)
  },
  { id: 'older-15', icon: '⏳', title: 'Историк', description: '«Что старше?»: серия из 15', test: (c) => (c.arcade.older ?? 0) >= 15 },
  { id: 'timeline-5', icon: '📅', title: 'Летописец', description: '«Хронология»: расставить все 5 песен верно', test: (c) => (c.arcade.timeline ?? 0) >= 5 },
  { id: 'quests-10', icon: '🎯', title: 'Исполнительный', description: 'Выполнить 10 ежедневных заданий', test: (c) => c.questsTotal >= 10 }
]

export function wonDecade(r: Round): string {
  return String(decadeOf(r.song.year))
}
