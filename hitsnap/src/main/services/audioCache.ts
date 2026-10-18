import { app } from 'electron'
import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { CacheInfo, ResolvedTrack, Song } from '@shared/types'
import { getBytes } from './http'
import { isAllowed } from './localMusic'
import { findPreview } from './providers'
import { storage } from './storage'

// Previews are kept on disk: a song heard once plays instantly (and offline) later.
// Provider URLs are signed and expire, so we keep the bytes, not the links.

const MAX_BYTES = 400 * 1024 * 1024

interface Meta {
  coverUrl?: string
  link?: string
  album?: string
  source: 'deezer' | 'itunes'
}

const dir = (): string => join(app.getPath('userData'), 'audio-cache')
const safe = (id: string): string => id.replace(/[^\wЀ-ӿ-]/g, '_')
const audioPath = (id: string): string => join(dir(), `${safe(id)}.audio`)
const metaPath = (id: string): string => join(dir(), `${safe(id)}.json`)

const inFlight = new Map<string, Promise<ResolvedTrack | null>>()

// Songs no provider has a preview for are remembered for a while, so the game
// does not waste time on them every session.
const UNAVAILABLE_KEY = 'unavailable-previews'
const UNAVAILABLE_DAYS = 14

function unavailable(): Record<string, number> {
  try {
    return JSON.parse(storage.get(UNAVAILABLE_KEY) ?? '{}') as Record<string, number>
  } catch {
    return {}
  }
}

function isUnavailable(id: string): boolean {
  const at = unavailable()[id]
  return !!at && Date.now() - at < UNAVAILABLE_DAYS * 86_400_000
}

function markUnavailable(id: string): void {
  void storage.set(UNAVAILABLE_KEY, JSON.stringify({ ...unavailable(), [id]: Date.now() }))
}

async function fromLocalFile(song: Song): Promise<ResolvedTrack | null> {
  if (!song.filePath || !isAllowed(song.filePath)) return null
  const buf = await readFile(song.filePath)
  const audio = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
  return { songId: song.id, audio, source: 'local' }
}

async function fromDisk(song: Song): Promise<ResolvedTrack | null> {
  try {
    const [buf, metaRaw] = await Promise.all([readFile(audioPath(song.id)), readFile(metaPath(song.id), 'utf8')])
    const meta = JSON.parse(metaRaw) as Meta
    const audio = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
    return { songId: song.id, audio, coverUrl: meta.coverUrl, link: meta.link, album: meta.album, source: 'cache' }
  } catch {
    return null
  }
}

async function download(song: Song): Promise<ResolvedTrack | null> {
  if (isUnavailable(song.id)) return null
  const info = await findPreview(song)
  if (!info) {
    markUnavailable(song.id)
    return null
  }
  const audio = await getBytes(info.previewUrl)
  const meta: Meta = { coverUrl: info.coverUrl, link: info.link, album: info.album, source: info.source }
  await mkdir(dir(), { recursive: true })
  await Promise.all([writeFile(audioPath(song.id), Buffer.from(audio)), writeFile(metaPath(song.id), JSON.stringify(meta))])
  void trim()
  return { songId: song.id, audio, ...meta }
}

export function resolveTrack(song: Song): Promise<ResolvedTrack | null> {
  const pending = inFlight.get(song.id)
  if (pending) return pending
  const job = (async () => {
    if (song.filePath) return fromLocalFile(song)
    return (await fromDisk(song)) ?? (await download(song))
  })().finally(() => inFlight.delete(song.id))
  inFlight.set(song.id, job)
  return job
}

async function listAudio(): Promise<Array<{ name: string; size: number; mtime: number }>> {
  try {
    const names = (await readdir(dir())).filter((n) => n.endsWith('.audio'))
    return Promise.all(
      names.map(async (name) => {
        const s = await stat(join(dir(), name))
        return { name, size: s.size, mtime: s.mtimeMs }
      })
    )
  } catch {
    return []
  }
}

/** Drops the oldest previews once the cache grows past MAX_BYTES. */
async function trim(): Promise<void> {
  const files = (await listAudio()).sort((a, b) => a.mtime - b.mtime)
  let total = files.reduce((sum, f) => sum + f.size, 0)
  for (const f of files) {
    if (total <= MAX_BYTES) break
    const base = f.name.slice(0, -'.audio'.length)
    await rm(join(dir(), f.name), { force: true })
    await rm(join(dir(), `${base}.json`), { force: true })
    total -= f.size
  }
}

export async function cacheInfo(): Promise<CacheInfo> {
  const files = await listAudio()
  const now = Date.now()
  return {
    files: files.length,
    bytes: files.reduce((sum, f) => sum + f.size, 0),
    songIds: files.map((f) => f.name.slice(0, -'.audio'.length)),
    unavailable: Object.entries(unavailable())
      .filter(([, at]) => now - at < UNAVAILABLE_DAYS * 86_400_000)
      .map(([id]) => id)
  }
}

export async function clearCache(): Promise<void> {
  await rm(dir(), { recursive: true, force: true })
  await storage.remove(UNAVAILABLE_KEY)
}
