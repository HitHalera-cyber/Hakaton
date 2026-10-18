import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
import { botStage, buildQueue, EMPTY_FILTERS, type GameConfig } from '@/lib/game'
import { passportFor } from '@/lib/passport'
import { createRng } from '@/lib/random'
import { daysLeftInWeek, weekKey, weeklyChallenge } from '@/lib/weekly'

describe('duel bot', () => {
  const rate = (level: 'easy' | 'pro') => {
    const rng = createRng(7)
    let first = 0
    for (let i = 0; i < 4000; i++) if (botStage(level, 2, rng) === 0) first++
    return first / 4000
  }
  it('a pro guesses from the first clip far more often than a beginner', () => {
    expect(rate('pro')).toBeGreaterThan(0.45)
    expect(rate('easy')).toBeLessThan(0.2)
  })
  it('returns a stage index or null', () => {
    const rng = createRng(1)
    for (let i = 0; i < 200; i++) expect([0, 1, 2, null]).toContain(botStage('mid', 1, rng))
  })
})

describe('weekly challenge', () => {
  it('keys a week by its Monday', () => {
    expect(weekKey(new Date(2026, 9, 18))).toBe('2026-10-12') // Sunday
    expect(weekKey(new Date(2026, 9, 12))).toBe('2026-10-12') // Monday
    expect(weekKey(new Date(2026, 9, 19))).toBe('2026-10-19')
    expect(daysLeftInWeek(new Date(2026, 9, 18))).toBe(1)
  })
  it('gives everyone the same songs that week', () => {
    const { key, theme, seed } = weeklyChallenge('2026-10-12')
    const config: GameConfig = {
      mode: 'classic',
      difficulty: 'normal',
      rounds: 10,
      filters: { ...EMPTY_FILTERS, ...theme.filters, popularity: 'popular' },
      seed,
      clipStart: 'random',
      weekKey: key
    }
    const a = buildQueue(CATALOG, config).slice(0, 10).map((s) => s.id)
    const b = buildQueue([...CATALOG].reverse(), config).slice(0, 10).map((s) => s.id)
    expect(a).toHaveLength(10)
    expect(b).toEqual(a)
  })
})

describe('music passport', () => {
  it('finds the favourite genre, decade and artists', () => {
    const queen = CATALOG.filter((s) => s.artist === 'Queen')
    const kino = CATALOG.find((s) => s.artist === 'Кино')!
    const songs = [...queen, kino]
    const stats: Record<string, { won: number }> = { [kino.id]: { won: 1 } }
    for (const s of queen) stats[s.id] = { won: 2 }
    const p = passportFor(songs, stats)
    expect(p.genre).toBe('rock')
    expect(p.artists[0].artist).toBe('Queen')
    expect(p.persona).toMatch(/^Рокер/)
  })
})
