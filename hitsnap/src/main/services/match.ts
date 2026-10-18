// Picks the search result that really is the requested song, so a karaoke
// cover or a different song with a similar name does not slip into the game.

export function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/ё/g, 'е')
    .replace(/\(.*?\)|\[.*?\]/g, ' ')
    .replace(/\b(feat|ft)\.?\b.*$/g, ' ')
    .replace(/[^a-z0-9а-я]+/g, ' ')
    .trim()
}

const COVER_WORDS = /karaoke|караоке|instrumental|tribute|cover|in the style of|made famous|minus|минус|8d|sped up|slowed|nightcore/i

function overlap(a: string, b: string): number {
  const wa = new Set(normalize(a).split(' ').filter(Boolean))
  const wb = new Set(normalize(b).split(' ').filter(Boolean))
  if (!wa.size || !wb.size) return 0
  let common = 0
  for (const w of wa) if (wb.has(w)) common++
  return common / Math.max(wa.size, wb.size)
}

export interface Candidate {
  artist: string
  title: string
  album?: string
}

/** 0..1 — how sure we are that the candidate is the wanted recording. */
export function matchScore(wantArtist: string, wantTitle: string, c: Candidate): number {
  if (COVER_WORDS.test(`${c.artist} ${c.title} ${c.album ?? ''}`) && !COVER_WORDS.test(wantTitle)) return 0
  const firstArtist = wantArtist.split(/\s*(?:&|,| feat\.? | x )\s*/i)[0]
  const artist = Math.max(overlap(wantArtist, c.artist), overlap(firstArtist, c.artist))
  const title = overlap(wantTitle, c.title)
  if (artist < 0.3 || title < 0.5) return 0
  return artist * 0.4 + title * 0.6
}
