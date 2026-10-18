import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useMemo } from 'react'
import { CATALOG } from '@shared/catalog'
import type { CatalogHit, Song } from '@shared/types'
import { buildIndex } from '@/lib/search'
import { diskStorage } from './persist'

// Songs the player added from the Deezer catalogue on top of the built-in base.

interface LibraryStore {
  custom: Song[]
  add: (hit: CatalogHit) => Song
  remove: (id: string) => void
}

export const useLibrary = create<LibraryStore>()(
  persist(
    (set, get) => ({
      custom: [],
      add: (hit) => {
        const song: Song = {
          id: `deezer-${hit.deezerId}`,
          artist: hit.artist,
          title: hit.title,
          year: hit.year ?? new Date().getFullYear(),
          genre: 'pop',
          lang: /[а-яё]/i.test(hit.artist + hit.title) ? 'ru' : 'en',
          deezerId: hit.deezerId,
          custom: true
        }
        if (!get().custom.some((s) => s.id === song.id)) set({ custom: [song, ...get().custom] })
        return song
      },
      remove: (id) => set({ custom: get().custom.filter((s) => s.id !== id) })
    }),
    { name: 'library', storage: diskStorage, version: 1 }
  )
)

export function allSongs(custom: Song[]): Song[] {
  const builtIn = new Set(CATALOG.map((s) => s.id))
  return [...CATALOG, ...custom.filter((s) => !builtIn.has(s.id))]
}

export function useAllSongs(): Song[] {
  const custom = useLibrary((s) => s.custom)
  return useMemo(() => allSongs(custom), [custom])
}

export function useSearchIndex() {
  const songs = useAllSongs()
  return useMemo(() => buildIndex(songs), [songs])
}
