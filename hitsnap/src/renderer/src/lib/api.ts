import type { CatalogHit, HitSnapApi, ResolvedTrack, Song } from '@shared/types'
import { CATALOG } from '@shared/catalog'
import { createRng, hashString } from './random'

// The Electron preload exposes `window.hitsnap`. Without it (the UI opened in a
// plain browser via `npm run dev:web`) a demo backend steps in: every song gets
// its own synthesised tune, so the whole game can be tried and tested offline.

export const isDemo = typeof window !== 'undefined' && !window.hitsnap

function synthesize(seedText: string, seconds = 30, rate = 22050): ArrayBuffer {
  const rng = createRng(hashString(seedText))
  const n = seconds * rate
  const samples = new Float32Array(n)
  const root = 196 * 2 ** (Math.floor(rng() * 12) / 12)
  const scale = rng() > 0.5 ? [0, 2, 4, 5, 7, 9, 11, 12] : [0, 2, 3, 5, 7, 8, 10, 12]
  const bpm = 84 + Math.floor(rng() * 70)
  const beat = 60 / bpm
  const motif = Array.from({ length: 8 }, () => scale[Math.floor(rng() * scale.length)])
  const progression = Array.from({ length: 4 }, () => scale[Math.floor(rng() * 6)])
  const wave = rng() > 0.5 ? (p: number) => Math.sin(p) : (p: number) => (Math.sin(p) + 0.3 * Math.sin(3 * p)) / 1.3
  for (let i = 0; i < n; i++) {
    const t = i / rate
    const b = t / beat
    const bar = Math.floor(b / 4)
    const step = Math.floor(b * 2)
    const inStep = (b * 2) % 1
    const note = motif[(step + bar) % motif.length] + (bar % 4 === 3 ? 2 : 0)
    const lead = wave(2 * Math.PI * root * 2 ** (note / 12) * t) * Math.exp(-inStep * 3) * 0.35
    const chord = progression[bar % 4]
    const bass = Math.sin(2 * Math.PI * (root / 2) * 2 ** (chord / 12) * t) * 0.25
    const kick = (b % 1) < 0.12 ? Math.sin(2 * Math.PI * 55 * t) * (1 - (b % 1) / 0.12) * 0.5 : 0
    samples[i] = (lead + bass + kick) * Math.min(1, t * 4)
  }
  const buf = new ArrayBuffer(44 + n * 2)
  const v = new DataView(buf)
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)))
  str(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); str(8, 'WAVE'); str(12, 'fmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true)
  str(36, 'data'); v.setUint32(40, n * 2, true)
  for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 0x6fff, true)
  return buf
}

const demoApi: HitSnapApi = {
  platform: 'web',
  async resolveTrack(song: Song): Promise<ResolvedTrack> {
    await new Promise((r) => setTimeout(r, 250))
    return { songId: song.id, audio: synthesize(song.id), source: 'cache' }
  },
  async searchCatalog(query: string): Promise<CatalogHit[]> {
    const q = query.toLowerCase()
    return CATALOG.filter((s) => `${s.artist} ${s.title}`.toLowerCase().includes(q))
      .slice(0, 12)
      .map((s, i) => ({ deezerId: 1000 + i, artist: s.artist, title: `${s.title} (Live)`, album: 'Demo', year: s.year }))
  },
  async cacheInfo() {
    return { files: 0, bytes: 0, songIds: [] }
  },
  async clearCache() {},
  async storageGet(key) {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  async storageSet(key, value) {
    try {
      localStorage.setItem(key, value)
    } catch {
      // storage unavailable — state lives for this session only
    }
  },
  async storageRemove(key) {
    try {
      localStorage.removeItem(key)
    } catch {
      // ignore
    }
  },
  async openExternal(url) {
    window.open(url, '_blank', 'noopener')
  },
  setTitleBarTheme() {}
}

export const api: HitSnapApi = (typeof window !== 'undefined' && window.hitsnap) || demoApi
