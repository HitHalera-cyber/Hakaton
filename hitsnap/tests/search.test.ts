import { describe, expect, it } from 'vitest'
import { CATALOG } from '@shared/catalog'
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
    expect(top('rbyj', 20)).toContain('Кино — Группа крови')
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
})
