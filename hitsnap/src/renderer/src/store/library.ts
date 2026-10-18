import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useMemo } from 'react'
import { CATALOG } from '@shared/catalog'
import type { CatalogHit, LocalTrack, RemotePlaylist, Song } from '@shared/types'
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

interface LibraryStore {
  custom: Song[]
  packs: Pack[]
  favorites: string[]
  localFolder: string | null
  localSongs: Song[]
  add: (hit: CatalogHit) => Song
  remove: (id: string) => void
  savePack: (playlist: RemotePlaylist) => Pack
  removePack: (id: string) => void
  toggleFavorite: (id: string) => void
  setLocal: (folder: string | null, tracks: LocalTrack[]) => void
}

const looksRussian = (text: string): boolean => /[а-яё]/i.test(text)

export function songFromHit(hit: CatalogHit): Song {
  return {
    id: `deezer-${hit.deezerId}`,
    artist: hit.artist,
    title: hit.title,
    year: hit.year ?? 0,
    genre: looksRussian(hit.artist + hit.title) ? 'russian-pop' : 'pop',
    lang: looksRussian(hit.artist + hit.title) ? 'ru' : 'en',
    tier: 2,
    deezerId: hit.deezerId,
    custom: true
  }
}

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
      remove: (id) => set({ custom: get().custom.filter((s) => s.id !== id) }),
      savePack: (playlist) => {
        const pack: Pack = {
          id: playlist.id,
          title: playlist.title,
          coverUrl: playlist.coverUrl,
          songs: playlist.tracks.map(songFromHit),
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
      setLocal: (folder, tracks) => set({ localFolder: folder, localSongs: tracks.map(songFromFile) })
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
