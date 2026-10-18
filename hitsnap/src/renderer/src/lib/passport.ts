import type { Genre, Song } from '@shared/types'
import { decadeOf } from './game'

// «Музыкальный паспорт»: who the player is as a listener, from the songs they guessed.

export interface Passport {
  wins: number
  genre: Genre | null
  decade: number | null
  artists: Array<{ artist: string; wins: number }>
  /** Share of guessed songs that are rare (tier 3), 0..1. */
  rare: number
  avgYear: number | null
  persona: string
}

const PERSONA: Record<Genre, string> = {
  pop: 'Поп-фанат',
  rock: 'Рокер',
  metal: 'Металлист',
  indie: 'Инди-душа',
  electronic: 'Тусовщик',
  disco: 'Диско-звезда',
  hiphop: 'Хип-хоп-голова',
  rnb: 'Соул-душа',
  jazz: 'Джазмен',
  country: 'Ковбой',
  latin: 'Латино-сердце',
  kpop: 'K-pop-стэн',
  soundtrack: 'Киноман',
  'russian-pop': 'Знаток эстрады',
  'russian-rock': 'Русский рокер',
  'russian-rap': 'Рэп-эксперт',
  soviet: 'Ретро-душа'
}

export const decadeLabel = (d: number): string => (d <= 1960 ? '60-х' : d >= 2000 ? `${d}-х` : `${String(d).slice(2)}-х`)

function top<K>(counts: Map<K, number>): K | null {
  let best: K | null = null
  let n = 0
  for (const [k, v] of counts) if (v > n) [best, n] = [k, v]
  return best
}

export function passportFor(songs: Song[], stats: Record<string, { won: number }>): Passport {
  const byId = new Map(songs.map((s) => [s.id, s]))
  const genres = new Map<Genre, number>()
  const decades = new Map<number, number>()
  const artists = new Map<string, number>()
  let wins = 0
  let rare = 0
  let years = 0
  let dated = 0
  for (const [id, st] of Object.entries(stats)) {
    const song = byId.get(id)
    if (!song || !st.won) continue
    wins += st.won
    genres.set(song.genre, (genres.get(song.genre) ?? 0) + st.won)
    artists.set(song.artist, (artists.get(song.artist) ?? 0) + st.won)
    if (song.tier === 3) rare += st.won
    if (song.year > 0) {
      decades.set(decadeOf(song.year), (decades.get(decadeOf(song.year)) ?? 0) + st.won)
      years += song.year * st.won
      dated += st.won
    }
  }
  const genre = top(genres)
  const decade = top(decades)
  return {
    wins,
    genre,
    decade,
    artists: [...artists.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 3)
      .map(([artist, n]) => ({ artist, wins: n })),
    rare: wins ? rare / wins : 0,
    avgYear: dated ? Math.round(years / dated) : null,
    persona: genre ? `${PERSONA[genre]}${decade ? ` ${decadeLabel(decade)}` : ''}` : 'Слушатель'
  }
}
