import type { CatalogHit, Genre, Lang, SongMeta, Tier } from '@shared/types'

// Sorts a song found on Deezer into the app's genres, eras and fame levels.
// Pure, so the UI tests cover it too.

export interface AlbumInfo {
  genres: string[]
  year?: number
}

/** Deezer genre names (any of the album's genres) → our genre. Order matters: first match wins. */
const GENRE_RULES: Array<[RegExp, Genre]> = [
  [/k-?pop|j-?pop|asian|корей|япон|anime/i, 'kpop'],
  [/film|game|soundtrack|кино|игр|саундтрек|classical|класси/i, 'soundtrack'],
  [/metal|метал/i, 'metal'],
  [/rap|hip.?hop|рэп|хип/i, 'hiphop'],
  [/latin|salsa|reggaet|mexic|brazil|bachata|латин/i, 'latin'],
  [/jazz|blues|джаз|блюз/i, 'jazz'],
  [/country|folk|bluegrass|кантри|фолк/i, 'country'],
  [/r&b|rnb|soul|funk|соул|фанк/i, 'rnb'],
  [/disco|диско/i, 'disco'],
  [/dance|electro|techno|house|trance|edm|электро|танц/i, 'electronic'],
  [/alternative|indie|альтерн|инди/i, 'indie'],
  [/rock|punk|рок|панк/i, 'rock']
]

const CYRILLIC = /[а-яё]/i
const OTHER_SCRIPT = /[Ͱ-Ͽ֐-׿؀-ۿ぀-ヿ㐀-鿿가-힯]|[àâçéèêëîïôûùüÿñæœäößåøáíóúãõ]/i

export function genreFromNames(names: string[], lang: Lang, year?: number): Genre {
  let genre: Genre = 'pop'
  for (const [rx, g] of GENRE_RULES) {
    if (names.some((n) => rx.test(n))) {
      genre = g
      break
    }
  }
  if (lang !== 'ru') return genre
  if (genre === 'hiphop') return 'russian-rap'
  if (genre === 'rock' || genre === 'metal' || genre === 'indie') return 'russian-rock'
  if (year && year < 1991) return 'soviet'
  return 'russian-pop'
}

export function langOf(artist: string, title: string): Lang {
  const text = `${artist} ${title}`
  if (CYRILLIC.test(text)) return 'ru'
  if (OTHER_SCRIPT.test(text)) return 'other'
  return 'en'
}

/** Deezer rank → how famous: chart hits rank ~800 000+, deep cuts below ~400 000. */
export function tierFromRank(rank?: number): Tier {
  if (!rank) return 2
  if (rank >= 800_000) return 1
  if (rank >= 450_000) return 2
  return 3
}

export function classifyTrack(hit: CatalogHit, album: AlbumInfo | null): SongMeta {
  const lang = langOf(hit.artist, hit.title)
  const year = album?.year ?? hit.year ?? 0
  return {
    genre: genreFromNames(album?.genres ?? [], lang, year),
    year,
    tier: tierFromRank(hit.rank),
    lang
  }
}
