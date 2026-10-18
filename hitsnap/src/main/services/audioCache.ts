import { app } from 'electron'
import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { CacheInfo, ResolvedTrack, Song } from '@shared/types'
import { getBytes } from './http'
import { findPreview } from './providers'

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
  const info = await findPreview(song)
  if (!info) return null
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
  const job = (async () => (await fromDisk(song)) ?? (await download(song)))().finally(() => inFlight.delete(song.id))
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
  return {
    files: files.length,
    bytes: files.reduce((sum, f) => sum + f.size, 0),
    songIds: files.map((f) => f.name.slice(0, -'.audio'.length))
  }
}

export async function clearCache(): Promise<void> {
  await rm(dir(), { recursive: true, force: true })
}
