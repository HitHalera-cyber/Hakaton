import type { Genre, Lang } from '../types'

/**
 * A block of songs sharing a genre and language. One song per line:
 *
 *   Artist | Title | Year            — tier 2 (popular) by default
 *   Artist | Title | Year | 1        — tier 1: a mega-hit everybody knows
 *   Artist | Title | Year | 3        — tier 3: for connoisseurs
 */
export interface Block {
  genre: Genre
  lang: Lang
  lines: string
}
