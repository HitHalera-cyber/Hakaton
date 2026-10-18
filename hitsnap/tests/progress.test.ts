import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
import type { GameConfig, Round } from '@/lib/game'
import { dailyStreak, levelFor, pointsForLevel, shareText } from '@/lib/progress'
import { parseTrackName } from '../src/main/services/trackName'

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
