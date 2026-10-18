import { describe, expect, it } from 'vitest'
import { matchScore } from '../src/main/services/match'

describe('provider result matching', () => {
  it('accepts the original recording', () => {
    expect(matchScore('Queen', 'Bohemian Rhapsody', { artist: 'Queen', title: 'Bohemian Rhapsody (Remastered 2011)' })).toBeGreaterThan(0.9)
    expect(matchScore('Кино', 'Группа крови', { artist: 'Кино', title: 'Группа крови' })).toBeGreaterThan(0.9)
  })

  it('rejects karaoke versions and other songs', () => {
    expect(matchScore('Queen', 'Bohemian Rhapsody', { artist: 'Karaoke Hits', title: 'Bohemian Rhapsody (Karaoke Version)' })).toBe(0)
    expect(matchScore('Queen', 'Bohemian Rhapsody', { artist: 'Queen', title: 'Radio Ga Ga' })).toBe(0)
  })

  it('matches a duet by its first artist', () => {
    expect(matchScore('Queen & David Bowie', 'Under Pressure', { artist: 'Queen', title: 'Under Pressure' })).toBeGreaterThan(0.6)
  })
})
