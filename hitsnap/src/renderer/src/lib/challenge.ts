import type { SoundEffect } from './audio'
import { EFFECTS } from './audio'
import { BOT_LEVELS, EMPTY_FILTERS, type BotLevel, type ClipStart, type Difficulty, type Filters, type GameMode } from './game'

// «Вызов другу»: a short code that recreates the same game — mode, filters,
// seed — with the sender's name and score, so a friend plays exactly the same
// songs and sees who did better.

export const CHALLENGE_MODES: GameMode[] = ['classic', 'quiz', 'artist', 'year', 'duel', 'blitz', 'survival']

export interface Challenge {
  mode: GameMode
  difficulty: Difficulty
  rounds: number
  filters: Filters
  seed: number
  clipStart: ClipStart
  effect: SoundEffect
  bot?: BotLevel
  /** Who sent it and what they scored (absent in a fresh code). */
  from?: { name: string; score: number; correct: number; total: number }
}

const PREFIX = 'HS-'

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64Url(code: string): string {
  const bin = atob(code.replace(/-/g, '+').replace(/_/g, '/'))
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)))
}

export function encodeChallenge(c: Challenge): string {
  const f = c.filters
  const data = {
    m: c.mode,
    d: c.difficulty,
    r: Number.isFinite(c.rounds) ? c.rounds : 0,
    f: [f.decades, f.genres, f.langs, f.popularity ?? 'all'],
    s: c.seed,
    c: c.clipStart,
    e: c.effect,
    b: c.bot,
    w: c.from && [c.from.name, c.from.score, c.from.correct, c.from.total]
  }
  return PREFIX + toBase64Url(JSON.stringify(data))
}

/** Reads a code; null if it is not a valid HitSnap challenge. */
export function decodeChallenge(raw: string): Challenge | null {
  const code = raw.trim().replace(/\s+/g, '')
  if (!code.toUpperCase().startsWith(PREFIX)) return null
  try {
    const d = JSON.parse(fromBase64Url(code.slice(PREFIX.length)))
    if (!CHALLENGE_MODES.includes(d.m) || !['easy', 'normal', 'hard'].includes(d.d) || typeof d.s !== 'number') return null
    const [decades, genres, langs, popularity] = Array.isArray(d.f) ? d.f : []
    const list = (x: unknown) => (Array.isArray(x) ? x : [])
    return {
      mode: d.m,
      difficulty: d.d,
      rounds: d.r > 0 ? Math.min(50, d.r) : Infinity,
      filters: { ...EMPTY_FILTERS, decades: list(decades), genres: list(genres), langs: list(langs), popularity: popularity ?? 'all' },
      seed: d.s >>> 0,
      clipStart: d.c === 'intro' ? 'intro' : 'random',
      effect: d.e in EFFECTS ? d.e : 'none',
      bot: d.b in BOT_LEVELS ? d.b : undefined,
      from: Array.isArray(d.w) ? { name: String(d.w[0] || 'Друг').slice(0, 24), score: Number(d.w[1]) || 0, correct: Number(d.w[2]) || 0, total: Number(d.w[3]) || 0 } : undefined
    }
  } catch {
    return null
  }
}
