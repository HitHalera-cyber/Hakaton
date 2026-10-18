import type { CatalogHit, ClassifiedHit, LookupResult, RemotePlaylist, Song } from '@shared/types'
import { classifyTrack, type AlbumInfo } from './classify'
import { getJson, resolveRedirect } from './http'
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
  album: { id?: number; title: string; cover_medium?: string; cover_big?: string }
  release_date?: string
  rank?: number
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

function toHit(t: DeezerTrack): CatalogHit {
  return {
    deezerId: t.id,
    artist: t.artist.name,
    title: t.title,
    album: t.album?.title ?? '',
    coverUrl: t.album?.cover_medium,
    year: t.release_date ? Number(t.release_date.slice(0, 4)) || undefined : undefined,
    albumId: t.album?.id,
    rank: t.rank
  }
}

/** Free-text search in the Deezer catalogue — used to add songs to «Мои песни». */
export async function searchCatalog(query: string): Promise<CatalogHit[]> {
  if (!query.trim()) return []
  return (await deezerSearch(query)).filter((t) => t.preview).map(toHit)
}

const MAX_PLAYLIST_TRACKS = 500

/** Accepts a playlist link (deezer.com/…/playlist/123, share links) or a bare id. */
async function playlistId(link: string): Promise<string> {
  const text = link.trim()
  if (/^\d+$/.test(text)) return text
  let url = text
  // Share links (link.deezer.com, deezer.page.link) redirect to the real playlist URL.
  if (!/\/playlist\/\d+/.test(url) && /^https:\/\//.test(url)) url = await resolveRedirect(url)
  const m = url.match(/\/playlist\/(\d+)/)
  if (!m) throw new Error('Не похоже на ссылку на плейлист Deezer')
  return m[1]
}

export async function fetchPlaylist(link: string): Promise<RemotePlaylist> {
  const id = await playlistId(link)
  const info = await getJson<{ id: number; title: string; picture_medium?: string; error?: { message?: string } }>(
    `https://api.deezer.com/playlist/${id}`
  )
  if (info.error) throw new Error(info.error.message ?? 'Плейлист не найден')
  const tracks: DeezerTrack[] = []
  for (let index = 0; index < MAX_PLAYLIST_TRACKS; index += 100) {
    const page = await getJson<{ data?: DeezerTrack[]; next?: string }>(
      `https://api.deezer.com/playlist/${id}/tracks?limit=100&index=${index}`
    )
    tracks.push(...(page.data ?? []))
    if (!page.next) break
  }
  return {
    id: `playlist-${id}`,
    title: info.title,
    coverUrl: info.picture_medium,
    tracks: tracks.filter((t) => t.preview).map(toHit)
  }
}

export async function fetchChart(): Promise<RemotePlaylist> {
  const res = await getJson<{ data?: DeezerTrack[] }>('https://api.deezer.com/chart/0/tracks?limit=100')
  return {
    id: 'chart',
    title: 'Чарт Deezer сейчас',
    tracks: (res.data ?? []).filter((t) => t.preview).map(toHit)
  }
}

// ——— Classification: genre and year come from the album, fame from the track's rank ———

const albums = new Map<number, Promise<AlbumInfo | null>>()

function albumInfo(id: number): Promise<AlbumInfo | null> {
  let p = albums.get(id)
  if (!p) {
    p = getJson<{ genres?: { data?: Array<{ id: number; name: string }> }; release_date?: string; error?: unknown }>(
      `https://api.deezer.com/album/${id}`
    )
      .then((a) => (a.error ? null : { genres: (a.genres?.data ?? []).map((g) => g.name), year: Number(a.release_date?.slice(0, 4)) || undefined }))
      .catch(() => null)
    albums.set(id, p)
  }
  return p
}

/** Deezer allows ~50 requests per 5 s: a few at a time with a short pause. */
async function mapThrottled<T, R>(items: T[], fn: (item: T) => Promise<R>, concurrency = 4): Promise<R[]> {
  const out: R[] = new Array(items.length)
  let next = 0
  const worker = async () => {
    while (next < items.length) {
      const i = next++
      out[i] = await fn(items[i])
      await new Promise((r) => setTimeout(r, 120))
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker))
  return out
}

/** Albums looked up per call; the rest of a huge playlist is classified from names and rank alone. */
const MAX_ALBUM_LOOKUPS = 150

export async function classify(hits: CatalogHit[]): Promise<ClassifiedHit[]> {
  const albumIds = [...new Set(hits.map((h) => h.albumId).filter((id): id is number => !!id))].slice(0, MAX_ALBUM_LOOKUPS)
  const infos = new Map<number, AlbumInfo | null>()
  await mapThrottled(albumIds, async (id) => infos.set(id, await albumInfo(id)))
  return hits.map((h) => ({ ...h, meta: classifyTrack(h, h.albumId ? (infos.get(h.albumId) ?? null) : null) }))
}

export async function lookup(queries: string[]): Promise<LookupResult[]> {
  const found = await mapThrottled(
    queries.slice(0, 200),
    async (query): Promise<{ query: string; hit: CatalogHit | null }> => {
      const [artist, ...rest] = query.split(/\s+[-–—]\s+/)
      const title = rest.join(' - ')
      try {
        const results = (await deezerSearch(title ? `artist:"${artist}" track:"${title}"` : query)).filter((t) => t.preview)
        const fallback = title && !results.length ? (await deezerSearch(`${artist} ${title}`)).filter((t) => t.preview) : results
        const hit = title
          ? best(fallback, (t) => matchScore(artist, title, { artist: t.artist.name, title: t.title, album: t.album?.title }))
          : (fallback[0] ?? null)
        return { query, hit: hit ? toHit(hit) : null }
      } catch {
        return { query, hit: null }
      }
    },
    3
  )
  const classified = await classify(found.flatMap((f) => (f.hit ? [f.hit] : [])))
  const byId = new Map(classified.map((c) => [c.deezerId, c]))
  return found.map((f) => ({ query: f.query, hit: f.hit ? (byId.get(f.hit.deezerId) ?? null) : null }))
}
