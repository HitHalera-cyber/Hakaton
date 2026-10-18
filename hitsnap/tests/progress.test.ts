import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
import type { GameConfig, Round } from '@/lib/game'
import { dailyStreak, levelFor, pointsForLevel, shareText } from '@/lib/progress'
import { parseTrackName } from '../src/main/services/trackName'
import { genreFromNames, langOf, tierFromRank } from '../src/main/services/classify'
import { advanceQuest, questsFor } from '@/lib/quests'

describe('levels', () => {
  it('starts at level 1 and grows with points', () => {
    expect(levelFor(0).level).toBe(1)
    expect(levelFor(pointsForLevel(2)).level).toBe(2)
    expect(levelFor(pointsForLevel(5) - 1).level).toBe(4)
    const l = levelFor(pointsForLevel(3) + 10)
    expect(l.progress).toBeGreaterThan(0)
    expect(l.progress).toBeLessThan(1)
  })
})

describe('daily streak', () => {
  it('counts consecutive days back from today or yesterday', () => {
    const today = new Date(2026, 9, 18)
    expect(dailyStreak(['2026-10-18', '2026-10-17', '2026-10-16'], today)).toBe(3)
    expect(dailyStreak(['2026-10-17', '2026-10-16'], today)).toBe(2)
    expect(dailyStreak(['2026-10-15'], today)).toBe(0)
  })
})

describe('share text', () => {
  it('sums up the game in one line of squares', () => {
    const s = CATALOG[0]
    const round = (status: Round['status'], stage: number): Round => ({
      song: s, offset: 0, stage, guesses: [], hints: 0, status, points: 0, startedAt: 0
    })
    const config = { mode: 'classic', difficulty: 'normal', rounds: 3, filters: { decades: [], genres: [], langs: [] }, seed: 1, clipStart: 'random' } as GameConfig
    const text = shareText(config, [round('won', 0), round('won', 2), round('lost', 2)], 1250)
    expect(text).toBe('HitSnap · Классика · 2/3 · 1 250 очков\n🟩🟧⬛')
  })
})

describe('own music file names', () => {
  it('reads "Artist - Title" and strips track numbers', () => {
    expect(parseTrackName('/m/01 - Queen - Bohemian Rhapsody.mp3', '/m')).toEqual({ artist: 'Queen', title: 'Bohemian Rhapsody' })
    expect(parseTrackName('/m/Кино – Группа крови.flac', '/m')).toEqual({ artist: 'Кино', title: 'Группа крови' })
    expect(parseTrackName('/music/Nirvana/03. Lithium.mp3', '/music/Nirvana')).toEqual({ artist: 'Nirvana', title: 'Lithium' })
  })
})

describe('auto classification of added songs', () => {
  it('maps Deezer album genres to the app genres', () => {
    expect(genreFromNames(['Rap/Hip Hop'], 'en')).toBe('hiphop')
    expect(genreFromNames(['Dance', 'Electro'], 'en')).toBe('electronic')
    expect(genreFromNames(['Metal', 'Rock'], 'en')).toBe('metal')
    expect(genreFromNames(['Films/Games'], 'en')).toBe('soundtrack')
    expect(genreFromNames([], 'en')).toBe('pop')
  })

  it('puts Russian songs into the Russian genres', () => {
    expect(genreFromNames(['Rap/Hip Hop'], 'ru')).toBe('russian-rap')
    expect(genreFromNames(['Rock'], 'ru')).toBe('russian-rock')
    expect(genreFromNames(['Pop'], 'ru', 1978)).toBe('soviet')
    expect(genreFromNames(['Pop'], 'ru', 2005)).toBe('russian-pop')
  })

  it('detects language and fame', () => {
    expect(langOf('Кино', 'Группа крови')).toBe('ru')
    expect(langOf('Stromae', 'Alors on danse')).toBe('en')
    expect(langOf('Indila', 'Dernière danse')).toBe('other')
    expect(tierFromRank(950_000)).toBe(1)
    expect(tierFromRank(500_000)).toBe(2)
    expect(tierFromRank(100_000)).toBe(3)
  })
})

describe('daily quests', () => {
  it('gives three different quests a day, the same for everyone', () => {
    const a = questsFor('2026-10-18')
    expect(a).toHaveLength(3)
    expect(new Set(a.map((q) => q.kind)).size).toBe(3)
    expect(questsFor('2026-10-18')).toEqual(a)
  })

  it('counts progress from game events', () => {
    const q = { id: 'x', kind: 'first-try' as const, title: '', target: 2, reward: 100 }
    const round = { song: CATALOG[0], offset: 0, stage: 0, guesses: [], hints: 0, status: 'won' as const, points: 0, startedAt: 0 }
    const e = { type: 'round' as const, round, mode: 'classic' as const, effect: 'none' as const, streak: 1 }
    expect(advanceQuest(q, 0, e)).toBe(1)
    expect(advanceQuest(q, 1, { ...e, round: { ...round, stage: 1 } })).toBe(1)
  })
})
