import type { CatalogHit, Song } from '@shared/types'
import { getJson } from './http'
import { matchScore } from './match'

export interface PreviewInfo {
  previewUrl: string
  coverUrl?: string
  link?: string
  album?: string
  source: 'deezer' | 'itunes'
}

// ——— Deezer: public API, no key; previews are 30 s MP3 ———

interface DeezerTrack {
  id: number
  title: string
  preview: string
  link: string
  artist: { name: string }
  album: { title: string; cover_medium?: string; cover_big?: string }
  release_date?: string
}

function fromDeezer(t: DeezerTrack): PreviewInfo {
  return {
    previewUrl: t.preview,
    coverUrl: t.album?.cover_big ?? t.album?.cover_medium,
    link: t.link,
    album: t.album?.title,
    source: 'deezer'
  }
}

async function deezerById(id: number): Promise<PreviewInfo | null> {
  const t = await getJson<DeezerTrack & { error?: unknown }>(`https://api.deezer.com/track/${id}`)
  return t.error || !t.preview ? null : fromDeezer(t)
}

async function deezerSearch(query: string): Promise<DeezerTrack[]> {
  const res = await getJson<{ data?: DeezerTrack[] }>(
    `https://api.deezer.com/search?limit=15&q=${encodeURIComponent(query)}`
  )
  return res.data ?? []
}

function best<T>(items: T[], score: (item: T) => number): T | null {
  let top: T | null = null
  let topScore = 0
  for (const item of items) {
    const s = score(item)
    if (s > topScore) {
      top = item
      topScore = s
    }
  }
  return top
}

async function deezerFind(song: Song): Promise<PreviewInfo | null> {
  const queries = [`artist:"${song.artist}" track:"${song.title}"`, `${song.artist} ${song.title}`]
  for (const q of queries) {
    const hits = (await deezerSearch(q)).filter((t) => t.preview)
    const hit = best(hits, (t) => matchScore(song.artist, song.title, { artist: t.artist.name, title: t.title, album: t.album?.title }))
    if (hit) return fromDeezer(hit)
  }
  return null
}

// ——— iTunes Search API: fallback, 30 s AAC previews ———

interface ItunesTrack {
  trackName: string
  artistName: string
  collectionName?: string
  previewUrl?: string
  artworkUrl100?: string
  trackViewUrl?: string
}

async function itunesFind(song: Song): Promise<PreviewInfo | null> {
  const res = await getJson<{ results?: ItunesTrack[] }>(
    `https://itunes.apple.com/search?media=music&entity=song&limit=15&term=${encodeURIComponent(`${song.artist} ${song.title}`)}`
  )
  const hits = (res.results ?? []).filter((t) => t.previewUrl)
  const hit = best(hits, (t) => matchScore(song.artist, song.title, { artist: t.artistName, title: t.trackName, album: t.collectionName }))
  if (!hit?.previewUrl) return null
  return {
    previewUrl: hit.previewUrl,
    coverUrl: hit.artworkUrl100?.replace('100x100', '500x500'),
    link: hit.trackViewUrl,
    album: hit.collectionName,
    source: 'itunes'
  }
}

/** Finds a playable preview for the song, trying every provider in turn. */
export async function findPreview(song: Song): Promise<PreviewInfo | null> {
  const attempts: Array<() => Promise<PreviewInfo | null>> = []
  if (song.deezerId) attempts.push(() => deezerById(song.deezerId!))
  attempts.push(() => deezerFind(song), () => itunesFind(song))
  let lastError: unknown = null
  for (const attempt of attempts) {
    try {
      const found = await attempt()
      if (found) return found
    } catch (err) {
      lastError = err
    }
  }
  if (lastError) throw lastError
  return null
}

/** Free-text search in the Deezer catalogue — used to add songs to «Мои песни». */
export async function searchCatalog(query: string): Promise<CatalogHit[]> {
  if (!query.trim()) return []
  const hits = await deezerSearch(query)
  return hits
    .filter((t) => t.preview)
    .map((t) => ({
      deezerId: t.id,
      artist: t.artist.name,
      title: t.title,
      album: t.album?.title ?? '',
      coverUrl: t.album?.cover_medium,
      year: t.release_date ? Number(t.release_date.slice(0, 4)) || undefined : undefined
    }))
}
