import type { Song, Tier } from '../types'
import type { Block } from './types'
import country from './data/country'
import disco from './data/disco'
import electronic from './data/electronic'
import hiphop from './data/hiphop'
import indie from './data/indie'
import jazz from './data/jazz'
import kpop from './data/kpop'
import latin from './data/latin'
import metal from './data/metal'
import pop from './data/pop'
import rnb from './data/rnb'
import rock from './data/rock'
import russianPop from './data/russian-pop'
import russianRap from './data/russian-rap'
import russianRock from './data/russian-rock'
import soundtrack from './data/soundtrack'
import soviet from './data/soviet'

// The built-in song base. Audio is not shipped with the app: the main process
// fetches each song's official 30-second preview (Deezer, then iTunes) on demand
// and caches it on disk.

const BLOCKS: Block[] = [
  ...pop,
  ...rock,
  ...metal,
  ...indie,
  ...electronic,
  ...disco,
  ...hiphop,
  ...rnb,
  ...jazz,
  ...country,
  ...latin,
  ...kpop,
  ...soundtrack,
  ...russianPop,
  ...russianRock,
  ...russianRap,
  ...soviet
]

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9а-яё]+/gi, '-')
    .replace(/^-+|-+$/g, '')
}

export function parseBlocks(blocks: Block[]): Song[] {
  const seen = new Set<string>()
  const songs: Song[] = []
  for (const { genre, lang, lines } of blocks) {
    for (const raw of lines.split('\n')) {
      const line = raw.trim()
      if (!line || line.startsWith('#')) continue
      const [artist, title, year, tier] = line.split('|').map((p) => p.trim())
      if (!artist || !title) continue
      const id = slugify(`${artist}-${title}`)
      if (seen.has(id)) continue
      seen.add(id)
      songs.push({
        id,
        artist,
        title,
        year: Number(year) || 0,
        genre,
        lang,
        tier: (Number(tier) || 2) as Tier
      })
    }
  }
  return songs
}

export const CATALOG: Song[] = parseBlocks(BLOCKS)
