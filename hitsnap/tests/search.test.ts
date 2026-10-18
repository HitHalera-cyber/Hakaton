import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
import { sameArtist } from '@/lib/game'
import { buildIndex, highlightRanges, search } from '@/lib/search'

const index = buildIndex(CATALOG)
const top = (q: string, n = 8) => search(index, q, n).map((s) => `${s.artist} — ${s.title}`)

describe('live search', () => {
  it('finds everything whose words start with the typed text', () => {
    const res = top('mich', 20)
    expect(res.some((r) => r.startsWith('Michael Jackson'))).toBe(true)
  })

  it('ranks a title prefix first', () => {
    expect(top('bohemian')[0]).toBe('Queen — Bohemian Rhapsody')
    expect(top('billie j')[0]).toBe('Michael Jackson — Billie Jean')
  })

  it('combines artist and title words', () => {
    expect(top('queen champions')[0]).toBe('Queen — We Are the Champions')
  })

  it('forgives typos', () => {
    expect(top('bohemain rapsody')).toContain('Queen — Bohemian Rhapsody')
    expect(top('smels like')).toContain('Nirvana — Smells Like Teen Spirit')
  })

  it('understands transliteration and the wrong keyboard layout', () => {
    expect(top('kino gruppa')[0]).toBe('Кино — Группа крови')
    expect(top('rbyj', 20).some((r) => r.startsWith('Кино — '))).toBe(true)
    expect(top('ьуефддшсф')[0]).toMatch(/^Metallica/) // "metallica" typed on ЙЦУКЕН
  })

  it('treats ё and е alike', () => {
    expect(top('пугачева')[0]).toMatch(/^Алла Пугачёва/)
  })

  it('returns nothing for an empty query', () => {
    expect(search(index, '   ')).toEqual([])
  })

  it('highlights word prefixes', () => {
    expect(highlightRanges('Smells Like Teen Spirit', 'li te')).toEqual([
      [7, 9],
      [12, 14]
    ])
  })
})

describe('catalog', () => {
  it('has a big base with unique ids', () => {
    expect(CATALOG.length).toBeGreaterThan(500)
    expect(new Set(CATALOG.map((s) => s.id)).size).toBe(CATALOG.length)
  })

  it('lists each song once, whoever is credited on it', () => {
    const byTitle = new Map<string, typeof CATALOG>()
    for (const s of CATALOG) {
      const key = s.title.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '')
      byTitle.set(key, [...(byTitle.get(key) ?? []), s])
    }
    const dups: string[] = []
    for (const songs of byTitle.values())
      songs.forEach((a, i) => songs.slice(i + 1).forEach((b) => sameArtist(a, b) && dups.push(`${a.artist} / ${b.artist} — ${a.title}`)))
    expect(dups).toEqual([])
  })
})

describe('search: names typed in the other alphabet, full result lists', () => {
  it('finds a foreign artist typed in Cyrillic', () => {
    const res = top('леди гага', 100)
    expect(res.length).toBeGreaterThan(5)
    expect(res.every((r) => r.includes('Lady Gaga'))).toBe(true)
    expect(top('квин', 5).some((r) => r.startsWith('Queen'))).toBe(true)
    expect(top('майкл джексон', 100).some((r) => r.startsWith('Michael Jackson'))).toBe(true)
    expect(top('бейонсе', 100).some((r) => r.startsWith('Beyoncé'))).toBe(true)
  })

  it('returns every song of an artist, not just the first few', () => {
    const all = CATALOG.filter((s) => s.artist === 'Queen').length
    expect(search(index, 'queen').filter((s) => s.artist === 'Queen').length).toBe(all)
  })
})
