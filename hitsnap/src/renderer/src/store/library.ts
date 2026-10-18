import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useMemo } from 'react'
import { CATALOG } from '@shared/catalog'
import type { CatalogHit, ClassifiedHit, LocalTrack, RemotePlaylist, Song } from '@shared/types'
import { hashString } from '@/lib/random'
import { buildIndex } from '@/lib/search'
import { diskStorage } from './persist'

// Everything the player brings on top of the built-in base: single songs
// added from Deezer, imported playlists and charts, their own music folder —
// plus favourites.

/** An imported Deezer playlist or chart. */
export interface Pack {
  id: string
  title: string
  coverUrl?: string
  songs: Song[]
  importedAt: number
}

/** Everything the player added, as a file they can back up or move to another computer. */
export interface LibraryExport {
  app: 'hitsnap'
  version: 1
  custom: Song[]
  packs: Pack[]
  favorites: string[]
}

interface LibraryStore {
  custom: Song[]
  packs: Pack[]
  favorites: string[]
  localFolder: string | null
  localSongs: Song[]
  add: (hit: CatalogHit | ClassifiedHit) => Song
  /** Adds several songs at once; returns how many were new. */
  addMany: (hits: Array<CatalogHit | ClassifiedHit>) => number
  /** Corrects what was detected automatically (genre, year, fame, language, names). */
  update: (id: string, patch: Partial<Pick<Song, 'artist' | 'title' | 'genre' | 'year' | 'tier' | 'lang'>>) => void
  remove: (id: string) => void
  savePack: (playlist: RemotePlaylist, classified?: ClassifiedHit[]) => Pack
  exportData: () => LibraryExport
  /** Merges a backup into the library; returns what was new. */
  importData: (data: unknown) => { songs: number; packs: number; favorites: number }
  removePack: (id: string) => void
  toggleFavorite: (id: string) => void
  setLocal: (folder: string | null, tracks: LocalTrack[]) => void
}

const looksRussian = (text: string): boolean => /[а-яё]/i.test(text)

export function songFromHit(hit: CatalogHit | ClassifiedHit): Song {
  const ru = looksRussian(hit.artist + hit.title)
  const meta = 'meta' in hit ? hit.meta : undefined
  return {
    id: `deezer-${hit.deezerId}`,
    artist: hit.artist,
    title: hit.title,
    year: meta?.year || hit.year || 0,
    genre: meta?.genre ?? (ru ? 'russian-pop' : 'pop'),
    lang: meta?.lang ?? (ru ? 'ru' : 'en'),
    tier: meta?.tier ?? 2,
    deezerId: hit.deezerId,
    custom: true
  }
}

const isSong = (x: unknown): x is Song =>
  !!x && typeof x === 'object' && typeof (x as Song).id === 'string' && typeof (x as Song).artist === 'string' && typeof (x as Song).title === 'string'

export function songFromFile(track: LocalTrack): Song {
  const ru = looksRussian(track.artist + track.title)
  return {
    id: `local-${hashString(track.path).toString(36)}`,
    artist: track.artist,
    title: track.title,
    year: 0,
    genre: ru ? 'russian-pop' : 'pop',
    lang: ru ? 'ru' : 'en',
    tier: 2,
    filePath: track.path,
    custom: true
  }
}

export const useLibrary = create<LibraryStore>()(
  persist(
    (set, get) => ({
      custom: [],
      packs: [],
      favorites: [],
      localFolder: null,
      localSongs: [],
      add: (hit) => {
        const song = songFromHit(hit)
        if (!get().custom.some((s) => s.id === song.id)) set({ custom: [song, ...get().custom] })
        return song
      },
      addMany: (hits) => {
        const known = new Set(get().custom.map((s) => s.id))
        const fresh = hits.map(songFromHit).filter((s) => !known.has(s.id) && (known.add(s.id), true))
        if (fresh.length) set({ custom: [...fresh, ...get().custom] })
        return fresh.length
      },
      update: (id, patch) => set({ custom: get().custom.map((s) => (s.id === id ? { ...s, ...patch } : s)) }),
      remove: (id) => set({ custom: get().custom.filter((s) => s.id !== id) }),
      savePack: (playlist, classified) => {
        const meta = new Map((classified ?? []).map((c) => [c.deezerId, c]))
        const pack: Pack = {
          id: playlist.id,
          title: playlist.title,
          coverUrl: playlist.coverUrl,
          songs: playlist.tracks.map((t) => songFromHit(meta.get(t.deezerId) ?? t)),
          importedAt: Date.now()
        }
        set({ packs: [pack, ...get().packs.filter((p) => p.id !== pack.id)] })
        return pack
      },
      removePack: (id) => set({ packs: get().packs.filter((p) => p.id !== id) }),
      toggleFavorite: (id) => {
        const favorites = get().favorites
        set({ favorites: favorites.includes(id) ? favorites.filter((f) => f !== id) : [id, ...favorites] })
      },
      setLocal: (folder, tracks) => set({ localFolder: folder, localSongs: tracks.map(songFromFile) }),
      exportData: () => {
        const { custom, packs, favorites } = get()
        return { app: 'hitsnap', version: 1, custom, packs, favorites }
      },
      importData: (data) => {
        const d = (data ?? {}) as Partial<LibraryExport>
        if (d.app !== 'hitsnap') throw new Error('Это не файл HitSnap')
        const custom = get().custom
        const known = new Set(custom.map((s) => s.id))
        const songs = (Array.isArray(d.custom) ? d.custom : []).filter(isSong).filter((s) => !known.has(s.id))
        const packIds = new Set(get().packs.map((p) => p.id))
        const packs = (Array.isArray(d.packs) ? d.packs : []).filter(
          (p): p is Pack => !!p && typeof p.id === 'string' && Array.isArray(p.songs) && !packIds.has(p.id)
        )
        const favSet = new Set(get().favorites)
        const favorites = (Array.isArray(d.favorites) ? d.favorites : []).filter((f): f is string => typeof f === 'string' && !favSet.has(f))
        set({
          custom: [...songs.map((s) => ({ ...s, custom: true, tier: s.tier ?? 2, filePath: undefined })), ...custom],
          packs: [...packs.map((p) => ({ ...p, songs: p.songs.filter(isSong) })), ...get().packs],
          favorites: [...get().favorites, ...favorites]
        })
        return { songs: songs.length, packs: packs.length, favorites: favorites.length }
      }
    }),
    { name: 'library', storage: diskStorage, version: 1 }
  )
)

/** The built-in base plus everything the player added — what search and answers work over. */
export function allSongs(custom: Song[], packs: Pack[], local: Song[]): Song[] {
  const seen = new Set(CATALOG.map((s) => s.id))
  const extra: Song[] = []
  for (const s of [...custom, ...packs.flatMap((p) => p.songs), ...local]) {
    if (seen.has(s.id)) continue
    seen.add(s.id)
    extra.push(s)
  }
  return extra.length ? [...CATALOG, ...extra] : CATALOG
}

export function useAllSongs(): Song[] {
  const custom = useLibrary((s) => s.custom)
  const packs = useLibrary((s) => s.packs)
  const local = useLibrary((s) => s.localSongs)
  return useMemo(() => allSongs(custom, packs, local), [custom, packs, local])
}

export function useSearchIndex() {
  const songs = useAllSongs()
  return useMemo(() => buildIndex(songs), [songs])
}

/** One entry per artist (a pseudo-song whose `title` is the name) for «Кто поёт?», plus song counts. */
export function useArtistIndex() {
  const songs = useAllSongs()
  return useMemo(() => {
    const artists = new Map<string, Song>()
    const counts = new Map<string, number>()
    for (const s of songs) {
      if (!artists.has(s.artist)) artists.set(s.artist, { ...s, id: `artist:${s.artist}`, title: s.artist, artist: '' })
      counts.set(s.artist, (counts.get(s.artist) ?? 0) + 1)
    }
    return { index: buildIndex([...artists.values()]), counts }
  }, [songs])
}
