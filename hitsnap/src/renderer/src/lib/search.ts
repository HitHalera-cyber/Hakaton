import type { Song } from '@shared/types'
import { editDistance, normalize, soundForm, soundKey, swapLayout, translit } from './text'

// Live search over the song base: "mick" → everything whose words start with
// "mick"; typos, transliteration ("kino" → «Кино») and a wrong keyboard layout
// ("rbyj") are forgiven.

interface Entry {
  song: Song
  title: string
  artist: string
  words: string[]
  titleWords: string[]
  /** Every word with its soundKey — finds «леди гага» → Lady Gaga. */
  sounds: Array<[key: string, form: string]>
  haystack: string
}

export interface SearchIndex {
  entries: Entry[]
}

function variants(text: string): string[] {
  const n = normalize(text)
  const t = translit(n)
  return t === n ? [n] : [n, t]
}

export function buildIndex(songs: Song[]): SearchIndex {
  return {
    entries: songs.map((song) => {
      const titles = variants(song.title)
      const artists = variants(song.artist)
      const titleWords = titles.flatMap((v) => v.split(' '))
      const words = [...titleWords, ...artists.flatMap((v) => v.split(' '))]
      return {
        song,
        title: titles[0],
        artist: artists[0],
        words,
        titleWords,
        sounds: [...new Set(words)].map((w): [string, string] => [soundKey(w), soundForm(w)]).filter(([k]) => k.length >= 2),
        haystack: [...titles, ...artists].join(' | ')
      }
    })
  }
}

/** Score for a Cyrillic token that sounds like a word of the entry; 0 if none does. */
function soundScore(e: Entry, tok: string): number {
  const key = soundKey(tok)
  if (key.length < 2) return 0
  const form = soundForm(tok)
  let best = 0
  for (const [k, w] of e.sounds) {
    if (!k.startsWith(key)) continue
    // The whole word sounding alike beats a prefix («квин» is Queen, not Kavinsky);
    // closer spelling breaks ties («бейонсе» is Beyoncé rather than "Bones").
    const close = editDistance(form, w.slice(0, form.length + 1), 2) <= 2 ? 4 : 0
    best = Math.max(best, (k === key ? 11 : 6) + close)
  }
  return best
}

const typoBudget = (tok: string): number => (tok.length >= 7 ? 2 : 1)

function scoreEntry(e: Entry, query: string, tokens: string[]): number {
  if (!tokens.length) return 0
  let score = 0
  let strong = true
  for (const tok of tokens) {
    if (e.titleWords.some((w) => w.startsWith(tok))) score += 30
    else if (e.words.some((w) => w.startsWith(tok))) score += 22
    else if (tok.length >= 3 && e.haystack.includes(tok)) score += 12
    else if (tok.length >= 4 && e.words.some((w) => editDistance(w.slice(0, tok.length), tok, typoBudget(tok)) <= typoBudget(tok))) {
      score += 8
      strong = false
    } else {
      // A foreign name typed in Cyrillic: compare how it sounds.
      const sound = tok.length >= 3 && /[а-я]/.test(tok) ? soundScore(e, tok) : 0
      if (!sound) return 0
      score += sound
      strong = false
    }
  }
  if (e.title.startsWith(query)) score += 40
  if (e.title === query) score += 40
  if (e.artist.startsWith(query)) score += 20
  if (`${e.artist} ${e.title}`.startsWith(query) || `${e.title} ${e.artist}`.startsWith(query)) score += 25
  if (strong) score += 10
  return score - e.title.length * 0.05
}

/** Songs matching the query, best first; `limit` defaults to all of them. */
export function search(index: SearchIndex, rawQuery: string, limit = Infinity): Song[] {
  const queries = [...new Set([normalize(rawQuery), translit(normalize(rawQuery)), normalize(swapLayout(rawQuery))])].filter(Boolean)
  if (!queries.length) return []
  const best = new Map<string, { song: Song; score: number }>()
  queries.forEach((q, qi) => {
    const tokens = q.split(' ')
    // Results through the layout swap rank below direct matches.
    const penalty = qi === 0 ? 0 : 5
    for (const e of index.entries) {
      const s = scoreEntry(e, q, tokens)
      if (s <= 0) continue
      const prev = best.get(e.song.id)
      if (!prev || prev.score < s - penalty) best.set(e.song.id, { song: e.song, score: s - penalty })
    }
  })
  return [...best.values()]
    .sort((a, b) => b.score - a.score || a.song.title.localeCompare(b.song.title))
    .slice(0, limit)
    .map((r) => r.song)
}

/** Character ranges of `text` to highlight for the query (word-prefix matches). */
export function highlightRanges(text: string, rawQuery: string): Array<[number, number]> {
  const tokens = normalize(rawQuery).split(' ').filter(Boolean)
  if (!tokens.length) return []
  const lower = text.toLowerCase().replace(/ё/g, 'е')
  const ranges: Array<[number, number]> = []
  const wordStart = /(^|[^\p{L}\p{N}])([\p{L}\p{N}])/gu
  for (const m of lower.matchAll(wordStart)) {
    const start = (m.index ?? 0) + m[1].length
    for (const tok of tokens) {
      if (lower.startsWith(tok, start)) {
        ranges.push([start, start + tok.length])
        break
      }
    }
  }
  return ranges
}
