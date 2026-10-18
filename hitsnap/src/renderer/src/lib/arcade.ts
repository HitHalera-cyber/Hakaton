import { normalize, translit } from './text'

// Pure rules of the Игротека games that need more than a few lines.

/** «Музыкальная лента»: can `year` go between the cards around `slot` (equal years fit either side)? */
export function fitsSlot(years: number[], slot: number, year: number): boolean {
  const before = slot > 0 ? years[slot - 1] : -Infinity
  const after = slot < years.length ? years[slot] : Infinity
  return before <= year && year <= after
}

export const BINGO_SIZE = 4

/** Indices of every line on the bingo card: rows, columns, both diagonals. */
const LINES: number[][] = [
  ...Array.from({ length: BINGO_SIZE }, (_, r) => Array.from({ length: BINGO_SIZE }, (_, c) => r * BINGO_SIZE + c)),
  ...Array.from({ length: BINGO_SIZE }, (_, c) => Array.from({ length: BINGO_SIZE }, (_, r) => r * BINGO_SIZE + c)),
  Array.from({ length: BINGO_SIZE }, (_, i) => i * BINGO_SIZE + i),
  Array.from({ length: BINGO_SIZE }, (_, i) => i * BINGO_SIZE + (BINGO_SIZE - 1 - i))
]

/** The completed line, if any. */
export function hasBingo(marked: boolean[]): number[] | null {
  return LINES.find((line) => line.every((i) => marked[i])) ?? null
}

// «Цепочка артистов» works across alphabets: «Кино» ends in "o", so "Oasis" fits.
// As in the Russian word game, ь/ъ/ы/й (and a final "y") are skipped.
const latin = (name: string): string => translit(normalize(name.replace(/^the\s+/i, ''))).replace(/[^a-z]/g, '')

export function firstLetter(name: string): string {
  return latin(name)[0] ?? ''
}

export function lastLetter(name: string): string {
  const s = latin(name).replace(/y+$/, '')
  return s[s.length - 1] ?? ''
}
