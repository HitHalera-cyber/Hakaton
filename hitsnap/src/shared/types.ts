// Types shared by the main process, the preload bridge and the UI.

export type Genre =
  | 'pop'
  | 'rock'
  | 'hiphop'
  | 'electronic'
  | 'rnb'
  | 'metal'
  | 'indie'
  | 'disco'
  | 'russian-pop'
  | 'russian-rock'
  | 'russian-rap'

export type Lang = 'en' | 'ru' | 'other'

export interface Song {
  id: string
  artist: string
  title: string
  year: number
  genre: Genre
  lang: Lang
  /** Exact Deezer track id — set for songs the user added from the Deezer catalogue. */
  deezerId?: number
  custom?: boolean
}

/** What the main process found for a song: the audio itself plus a little metadata. */
export interface ResolvedTrack {
  songId: string
  audio: ArrayBuffer
  coverUrl?: string
  link?: string
  album?: string
  source: 'deezer' | 'itunes' | 'cache'
}

export interface CatalogHit {
  deezerId: number
  artist: string
  title: string
  album: string
  coverUrl?: string
  year?: number
}

export interface CacheInfo {
  files: number
  bytes: number
  songIds: string[]
}

export interface HitSnapApi {
  platform: string
  resolveTrack(song: Song): Promise<ResolvedTrack | null>
  searchCatalog(query: string): Promise<CatalogHit[]>
  cacheInfo(): Promise<CacheInfo>
  clearCache(): Promise<void>
  storageGet(key: string): Promise<string | null>
  storageSet(key: string, value: string): Promise<void>
  storageRemove(key: string): Promise<void>
  openExternal(url: string): Promise<void>
  setTitleBarTheme(dark: boolean): void
}
