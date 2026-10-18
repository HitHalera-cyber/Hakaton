// Types shared by the main process, the preload bridge and the UI.

export type Genre =
  | 'pop'
  | 'rock'
  | 'metal'
  | 'indie'
  | 'electronic'
  | 'disco'
  | 'hiphop'
  | 'rnb'
  | 'jazz'
  | 'country'
  | 'latin'
  | 'kpop'
  | 'soundtrack'
  | 'russian-pop'
  | 'russian-rock'
  | 'russian-rap'
  | 'soviet'

export type Lang = 'en' | 'ru' | 'other'

/** How well known a song is: 1 — everybody knows it, 2 — popular, 3 — for connoisseurs. */
export type Tier = 1 | 2 | 3

export interface Song {
  id: string
  artist: string
  title: string
  year: number
  genre: Genre
  lang: Lang
  tier: Tier
  /** Exact Deezer track id — set for songs the user added from Deezer (search, playlists, charts). */
  deezerId?: number
  /** Absolute path of a file from the player's own music folder. */
  filePath?: string
  custom?: boolean
}

/** What the main process found for a song: the audio itself plus a little metadata. */
export interface ResolvedTrack {
  songId: string
  audio: ArrayBuffer
  coverUrl?: string
  link?: string
  album?: string
  source: 'deezer' | 'itunes' | 'cache' | 'local'
}

export interface CatalogHit {
  deezerId: number
  artist: string
  title: string
  album: string
  coverUrl?: string
  year?: number
  albumId?: number
  /** Deezer popularity, 0..~1 000 000. */
  rank?: number
}

/** What the app worked out about a song: genre, year, how famous, language. */
export interface SongMeta {
  genre: Genre
  year: number
  tier: Tier
  lang: Lang
}

export interface ClassifiedHit extends CatalogHit {
  meta: SongMeta
}

/** One line of a bulk add («Исполнитель - Название») and what was found for it. */
export interface LookupResult {
  query: string
  hit: ClassifiedHit | null
}

/** A Deezer playlist or chart brought into the app. */
export interface RemotePlaylist {
  id: string
  title: string
  coverUrl?: string
  tracks: CatalogHit[]
}

/** A file found in the player's own music folder. */
export interface LocalTrack {
  path: string
  artist: string
  title: string
}

export interface CacheInfo {
  files: number
  bytes: number
  songIds: string[]
  /** Songs no provider had a preview for (skipped by the game for a while). */
  unavailable: string[]
}

export interface HitSnapApi {
  platform: string
  resolveTrack(song: Song): Promise<ResolvedTrack | null>
  searchCatalog(query: string): Promise<CatalogHit[]>
  /** A Deezer playlist by link or id. */
  fetchPlaylist(link: string): Promise<RemotePlaylist>
  /** Deezer's current top-100 chart. */
  fetchChart(): Promise<RemotePlaylist>
  /** Works out genre, year, popularity and language for Deezer tracks. */
  classify(hits: CatalogHit[]): Promise<ClassifiedHit[]>
  /** Finds songs by free text («Исполнитель - Название», one per entry) and classifies them. */
  lookup(queries: string[]): Promise<LookupResult[]>
  /** Lets the player choose a music folder; null when cancelled. */
  pickMusicFolder(): Promise<string | null>
  /** Audio files of a folder chosen earlier with pickMusicFolder. */
  scanMusicFolder(folder: string): Promise<LocalTrack[]>
  cacheInfo(): Promise<CacheInfo>
  clearCache(): Promise<void>
  storageGet(key: string): Promise<string | null>
  storageSet(key: string, value: string): Promise<void>
  storageRemove(key: string): Promise<void>
  openExternal(url: string): Promise<void>
  setTitleBarTheme(dark: boolean): void
  toggleFullScreen(): void
}
