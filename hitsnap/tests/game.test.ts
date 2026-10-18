import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
import type { Song } from '@shared/types'
import { buildQueue, EMPTY_FILTERS, isCorrect, matchesFilters, matchesPopularity, pickOffset, pointsFor, quizOptions, sameArtist, seedFor, yearCloseness, type GameConfig } from '@/lib/game'
import { createRng, todayKey } from '@/lib/random'

const song = (artist: string, title: string, extra: Partial<Song> = {}): Song => ({
  id: `${artist}-${title}`,
  artist,
  title,
  year: 2000,
  genre: 'pop',
  lang: 'en',
  tier: 2,
  ...extra
})

const config = (patch: Partial<GameConfig> = {}): GameConfig => ({
  mode: 'classic',
  difficulty: 'normal',
  rounds: 10,
  filters: EMPTY_FILTERS,
  seed: 42,
  clipStart: 'random',
  ...patch
})

describe('scoring', () => {
  it('pays more for earlier guesses', () => {
    expect(pointsFor(0, 0, 0)).toBe(1000)
    expect(pointsFor(1, 0, 0)).toBe(500)
    expect(pointsFor(2, 0, 0)).toBe(250)
  })

  it('adds a capped streak bonus and takes hints off', () => {
    expect(pointsFor(0, 2, 0)).toBe(1200)
    expect(pointsFor(0, 50, 0)).toBe(1500)
    expect(pointsFor(0, 0, 1)).toBe(800)
  })
})

describe('answers', () => {
  it('accepts the same song from a duplicate entry', () => {
    expect(isCorrect(song('Queen', 'Bohemian Rhapsody'), song('Queen', 'Bohemian Rhapsody', { id: 'x' }))).toBe(true)
  })

  it('rejects a same-titled song by another artist', () => {
    expect(isCorrect(song('Bon Jovi', "It's My Life"), song('Dr. Alban', "It's My Life"))).toBe(false)
  })

  it('notices the right artist with the wrong song', () => {
    expect(sameArtist(song('Queen & David Bowie', 'Under Pressure'), song('David Bowie', 'Heroes'))).toBe(true)
    expect(sameArtist(song('The Killers', 'Mr. Brightside'), song('Killers', 'x'))).toBe(true)
    expect(sameArtist(song('Queen', 'a'), song('ABBA', 'b'))).toBe(false)
  })
})

describe('queue', () => {
  it('applies filters', () => {
    const q = buildQueue(CATALOG, config({ filters: { decades: [1980], genres: [], langs: [] } }))
    expect(q.length).toBeGreaterThan(20)
    expect(q.every((s) => s.year >= 1980 && s.year < 1990)).toBe(true)
  })

  it('puts recently heard songs last', () => {
    const recent = CATALOG.slice(0, 50).map((s) => s.id)
    const q = buildQueue(CATALOG, config(), recent)
    expect(q.slice(0, CATALOG.length - 50).some((s) => recent.includes(s.id))).toBe(false)
  })

  it('gives everyone the same daily songs', () => {
    const key = todayKey(new Date(2026, 9, 18))
    const a = buildQueue(CATALOG, config({ mode: 'daily', seed: seedFor('daily', key) }), ['whatever'])
    const b = buildQueue([...CATALOG].reverse(), config({ mode: 'daily', seed: seedFor('daily', key) }))
    expect(a.slice(0, 5).map((s) => s.id)).toEqual(b.slice(0, 5).map((s) => s.id))
  })

  it('filters by language', () => {
    expect(CATALOG.filter((s) => matchesFilters(s, { decades: [], genres: [], langs: ['ru'] })).every((s) => s.lang === 'ru')).toBe(true)
  })
})

describe('clip offset', () => {
  it('stays inside the preview with room for the longest clip', () => {
    const rng = createRng(7)
    for (let i = 0; i < 200; i++) {
      const o = pickOffset(30, 5, rng)
      expect(o).toBeGreaterThanOrEqual(2)
      expect(o + 5).toBeLessThanOrEqual(30)
    }
    expect(pickOffset(3, 5, rng)).toBe(0)
  })
})

describe('popularity', () => {
  it('splits the base into hits, popular and rare songs', () => {
    const hits = CATALOG.filter((s) => matchesPopularity(s, 'hits'))
    const popular = CATALOG.filter((s) => matchesPopularity(s, 'popular'))
    const rare = CATALOG.filter((s) => matchesPopularity(s, 'rare'))
    expect(hits.length).toBeGreaterThan(150)
    expect(popular.length).toBeGreaterThan(hits.length)
    expect(rare.length + popular.length).toBe(CATALOG.length)
    expect(hits.some((s) => s.title === 'Bohemian Rhapsody')).toBe(true)
  })
})

describe('quiz', () => {
  it('offers four different answers including the right one', () => {
    const answer = CATALOG.find((s) => s.title === 'Bohemian Rhapsody')!
    const options = quizOptions(answer, CATALOG, createRng(3))
    expect(options).toHaveLength(4)
    expect(options).toContainEqual(answer)
    expect(new Set(options.map((o) => o.artist)).size).toBe(4)
    expect(options.filter((o) => o.id !== answer.id).every((o) => o.genre === answer.genre)).toBe(true)
  })
})

describe('year mode', () => {
  it('rewards close answers', () => {
    expect(yearCloseness(1985, 1985)).toBe(1)
    expect(yearCloseness(1986, 1985)).toBeGreaterThan(yearCloseness(1988, 1985))
    expect(yearCloseness(2000, 1985)).toBe(0)
  })

  it('only asks songs with a known year', () => {
    const pool = [song('A', 'x', { year: 0 }), song('B', 'y', { year: 1999 })]
    expect(buildQueue(pool, config({ mode: 'year' })).map((s) => s.artist)).toEqual(['B'])
  })
})
