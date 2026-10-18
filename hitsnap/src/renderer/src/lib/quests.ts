import type { Genre } from '@shared/types'
import type { SoundEffect } from './audio'
import { decadeOf, GENRE_LABELS, MODE_INFO, type GameMode, type Round } from './game'
import { createRng, hashString, shuffle, todayKey } from './random'

// Three small goals a day, the same for everybody on that date, with XP as a reward.

export type ArcadeGame = 'older' | 'timeline' | 'whose' | 'odd' | 'cover' | 'missing'

export const ARCADE_INFO: Record<ArcadeGame, { title: string; subtitle: string; emoji: string }> = {
  older: { title: 'Что старше?', subtitle: 'Из двух песен выберите ту, что вышла раньше', emoji: '⏳' },
  timeline: { title: 'Хронология', subtitle: 'Расставьте пять песен по году выхода', emoji: '📅' },
  whose: { title: 'Чья песня?', subtitle: 'По трём названиям угадайте исполнителя', emoji: '🎤' },
  odd: { title: 'Найди лишнее', subtitle: 'Три песни из одного десятилетия, одна — нет', emoji: '🔍' },
  cover: { title: 'По обложке', subtitle: 'Обложка проясняется на глазах — узнайте песню раньше', emoji: '🖼️' },
  missing: { title: 'Допиши название', subtitle: 'В названии пропало слово — какое?', emoji: '✍️' }
}

export type QuestKind = 'wins' | 'win-genre' | 'win-decade' | 'first-try' | 'play-mode' | 'streak' | 'effect' | 'arcade'

export interface Quest {
  id: string
  kind: QuestKind
  title: string
  target: number
  reward: number
  genre?: Genre
  decade?: number
  mode?: GameMode
  arcade?: ArcadeGame
}

export type QuestEvent =
  | { type: 'round'; round: Round; mode: GameMode; effect: SoundEffect; streak: number }
  | { type: 'game'; mode: GameMode }
  | { type: 'arcade'; game: ArcadeGame; score: number }

const QUEST_GENRES: Genre[] = ['pop', 'rock', 'electronic', 'hiphop', 'russian-pop', 'russian-rock', 'disco', 'metal', 'soviet', 'indie']
const QUEST_DECADES = [1970, 1980, 1990, 2000, 2010]
const QUEST_MODES: GameMode[] = ['quiz', 'year', 'artist', 'blitz', 'survival']

export function questsFor(day = todayKey()): Quest[] {
  const rng = createRng(hashString(`hitsnap-quests-${day}`))
  const pick = <T>(xs: T[]): T => xs[Math.floor(rng() * xs.length)]
  const make: Record<QuestKind, () => Omit<Quest, 'id' | 'kind'>> = {
    wins: () => ({ title: 'Угадайте 10 песен в любых режимах', target: 10, reward: 400 }),
    'win-genre': () => {
      const genre = pick(QUEST_GENRES)
      return { title: `Угадайте 3 песни в жанре «${GENRE_LABELS[genre]}»`, target: 3, reward: 450, genre }
    },
    'win-decade': () => {
      const decade = pick(QUEST_DECADES)
      return { title: `Угадайте 4 песни ${decade === 2000 ? '2000-х' : `${String(decade).slice(2)}-х`}`, target: 4, reward: 450, decade }
    },
    'first-try': () => ({ title: 'Угадайте 2 песни с первой попытки', target: 2, reward: 500 }),
    'play-mode': () => {
      const mode = pick(QUEST_MODES)
      return { title: `Сыграйте в режим «${MODE_INFO[mode].title}»`, target: 1, reward: 300, mode }
    },
    streak: () => ({ title: 'Соберите серию из 5 угаданных подряд', target: 5, reward: 600 }),
    effect: () => ({ title: 'Угадайте 2 песни со звуковым эффектом', target: 2, reward: 550 }),
    arcade: () => {
      const arcade = pick(Object.keys(ARCADE_INFO) as ArcadeGame[])
      return { title: `Сыграйте в «${ARCADE_INFO[arcade].title}» в Игротеке`, target: 1, reward: 300, arcade }
    }
  }
  const kinds = shuffle(Object.keys(make) as QuestKind[], rng).slice(0, 3)
  return kinds.map((kind) => ({ id: `${day}-${kind}`, kind, ...make[kind]() }))
}

/** New progress value of a quest after an event. */
export function advanceQuest(q: Quest, current: number, e: QuestEvent): number {
  if (e.type === 'round') {
    const won = e.round.status === 'won'
    switch (q.kind) {
      case 'wins':
        return current + (won ? 1 : 0)
      case 'win-genre':
        return current + (won && e.round.song.genre === q.genre ? 1 : 0)
      case 'win-decade':
        return current + (won && e.round.song.year > 0 && decadeOf(e.round.song.year) === q.decade ? 1 : 0)
      case 'first-try':
        return current + (won && e.round.stage === 0 ? 1 : 0)
      case 'streak':
        return Math.max(current, e.streak)
      case 'effect':
        return current + (won && e.effect !== 'none' ? 1 : 0)
      default:
        return current
    }
  }
  if (e.type === 'game' && q.kind === 'play-mode') return current + (e.mode === q.mode ? 1 : 0)
  if (e.type === 'arcade' && q.kind === 'arcade') return current + (e.game === q.arcade ? 1 : 0)
  return current
}
