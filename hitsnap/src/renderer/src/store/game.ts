import { create } from 'zustand'
import type { Song } from '@shared/types'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { api } from '@/lib/api'
import { audio } from '@/lib/audio'
import {
  buildQueue,
  isCorrect,
  MAX_HINTS,
  pickOffset,
  pointsFor,
  sameArtist,
  STAGES,
  SURVIVAL_LIVES,
  type GameConfig,
  type Round
} from '@/lib/game'
import { createRng } from '@/lib/random'
import { useSettings } from './settings'
import { useStats } from './stats'
import { useUi } from './ui'

// The game state machine:
//   loading → playing ⇄ (guess / skip / hint) → reveal → loading … → finished

export type Phase = 'idle' | 'loading' | 'playing' | 'reveal' | 'finished' | 'error'

interface Loaded {
  song: Song
  buffer: AudioBuffer
  coverUrl?: string
  link?: string
  album?: string
}

interface GameStore {
  phase: Phase
  config: GameConfig | null
  queue: Song[]
  cursor: number
  rounds: Round[]
  buffer: AudioBuffer | null
  score: number
  streak: number
  bestStreak: number
  lives: number
  lastPoints: number
  error: string | null
  start: (config: GameConfig, pool: Song[]) => Promise<void>
  playStage: () => void
  playReveal: () => void
  guess: (song: Song) => void
  skip: () => void
  hint: () => void
  next: () => Promise<void>
  finish: () => void
  quit: () => void
}

const MAX_FAILURES = 6

let session = 0
const prefetched = new Map<string, Promise<Loaded | null>>()
let rng = createRng(1)

async function load(song: Song): Promise<Loaded | null> {
  const track = await api.resolveTrack(song)
  if (!track) return null
  const buffer = await audio.decode(track.audio)
  return { song, buffer, coverUrl: track.coverUrl, link: track.link, album: track.album }
}

function loadCached(song: Song): Promise<Loaded | null> {
  let p = prefetched.get(song.id)
  if (!p) {
    p = load(song).catch(() => null)
    prefetched.set(song.id, p)
  }
  return p
}

function stagesOf(config: GameConfig): number[] {
  return STAGES[config.mode === 'daily' ? 'normal' : config.difficulty]
}

function notifyAchievements(ids: string[]): void {
  const { toast } = useUi.getState()
  for (const id of ids) {
    const a = ACHIEVEMENTS.find((x) => x.id === id)
    if (a) toast({ title: `Достижение: ${a.title}`, body: a.description, icon: a.icon, tone: 'success' })
  }
}

export const useGame = create<GameStore>()((set, get) => {
  const current = (): Round | null => {
    const { rounds } = get()
    return rounds.length ? rounds[rounds.length - 1] : null
  }

  const updateCurrent = (patch: Partial<Round>): void => {
    const rounds = [...get().rounds]
    rounds[rounds.length - 1] = { ...rounds[rounds.length - 1], ...patch }
    set({ rounds })
  }

  const isOver = (): boolean => {
    const { config, rounds, lives } = get()
    if (!config) return true
    if (config.mode === 'survival') return lives <= 0
    return rounds.length >= config.rounds
  }

  /** Loads the next playable song, skipping ones without a preview. */
  const loadNextRound = async (): Promise<void> => {
    const id = session
    const { config } = get()
    if (!config) return
    set({ phase: 'loading', buffer: null })
    let failures = 0
    let cursor = get().cursor
    const queue = get().queue
    while (cursor < queue.length) {
      const song = queue[cursor++]
      // Warm up the following song while this one is being prepared.
      if (queue[cursor]) void loadCached(queue[cursor])
      const loaded = await loadCached(song)
      prefetched.delete(song.id)
      if (id !== session) return
      if (!loaded) {
        if (++failures >= MAX_FAILURES) {
          set({
            phase: 'error',
            cursor,
            error: 'Не удаётся загрузить песни. Проверьте подключение к интернету — без сети доступны только уже прослушанные песни.'
          })
          return
        }
        continue
      }
      const stages = stagesOf(config)
      const round: Round = {
        song,
        offset: pickOffset(loaded.buffer.duration, stages[stages.length - 1], rng),
        stage: 0,
        guesses: [],
        hints: 0,
        status: 'playing',
        points: 0,
        startedAt: Date.now(),
        coverUrl: loaded.coverUrl,
        link: loaded.link,
        album: loaded.album
      }
      set({ phase: 'playing', cursor, buffer: loaded.buffer, rounds: [...get().rounds, round] })
      if (queue[cursor]) void loadCached(queue[cursor])
      if (useSettings.getState().autoplay) get().playStage()
      return
    }
    set({ cursor })
    if (get().rounds.length) get().finish()
    else set({ phase: 'error', error: 'Под выбранные фильтры не нашлось ни одной песни. Ослабьте фильтры и попробуйте снова.' })
  }

  const endRound = (won: boolean): void => {
    const { config, streak } = get()
    const round = current()
    if (!config || !round) return
    const scored = config.mode !== 'practice'
    const points = won && scored ? pointsFor(round.stage, streak, round.hints) : 0
    const newStreak = won ? streak + 1 : 0
    const lives = config.mode === 'survival' && !won ? get().lives - 1 : get().lives
    updateCurrent({ status: won ? 'won' : 'lost', points, endedAt: Date.now() })
    set({
      phase: 'reveal',
      score: get().score + points,
      lastPoints: points,
      streak: newStreak,
      bestStreak: Math.max(get().bestStreak, newStreak),
      lives
    })
    const finished = current()!
    const settings = useSettings.getState()
    if (settings.sfx) audio.sfx(won ? 'correct' : 'wrong')
    // Let the answer cue sound, then keep the song playing from the clip start.
    setTimeout(() => {
      if (get().phase === 'reveal' && current() === finished) get().playReveal()
    }, settings.sfx ? 350 : 0)
    const stats = useStats.getState()
    const unlocked = stats.recordRound(finished, scored)
    if (scored) stats.noteStreak(newStreak)
    notifyAchievements(unlocked)
  }

  const advanceStage = (): void => {
    const { config } = get()
    const round = current()
    if (!config || !round) return
    if (round.stage + 1 >= stagesOf(config).length) {
      endRound(false)
      return
    }
    updateCurrent({ stage: round.stage + 1 })
    if (useSettings.getState().autoplay) setTimeout(() => get().phase === 'playing' && get().playStage(), 450)
  }

  return {
    phase: 'idle',
    config: null,
    queue: [],
    cursor: 0,
    rounds: [],
    buffer: null,
    score: 0,
    streak: 0,
    bestStreak: 0,
    lives: SURVIVAL_LIVES,
    lastPoints: 0,
    error: null,

    start: async (config, pool) => {
      session++
      audio.stop()
      prefetched.clear()
      rng = createRng(config.seed ^ 0x9e3779b9)
      const recent = config.mode === 'daily' ? [] : useStats.getState().recent
      let queue = buildQueue(pool, config, recent)
      // Offline: put songs that are already on disk first.
      if (!navigator.onLine) {
        const cached = new Set((await api.cacheInfo()).songIds)
        queue = [...queue.filter((s) => cached.has(s.id)), ...queue.filter((s) => !cached.has(s.id))]
      }
      set({
        phase: 'loading',
        config,
        queue,
        cursor: 0,
        rounds: [],
        buffer: null,
        score: 0,
        streak: 0,
        bestStreak: 0,
        lives: SURVIVAL_LIVES,
        lastPoints: 0,
        error: null
      })
      useUi.getState().go('game')
      await loadNextRound()
    },

    playStage: () => {
      const { buffer, config } = get()
      const round = current()
      if (!buffer || !config || !round) return
      audio.play(buffer, round.offset, stagesOf(config)[round.stage])
    },

    playReveal: () => {
      const { buffer } = get()
      const round = current()
      if (!buffer || !round) return
      audio.play(buffer, round.offset)
    },

    guess: (song) => {
      const round = current()
      if (get().phase !== 'playing' || !round) return
      const correct = isCorrect(round.song, song)
      const guess = { songId: song.id, label: `${song.artist} — ${song.title}`, stage: round.stage, sameArtist: !correct && sameArtist(round.song, song) }
      updateCurrent({ guesses: [...round.guesses, guess] })
      if (correct) {
        audio.stop()
        endRound(true)
      } else {
        if (useSettings.getState().sfx) audio.sfx('wrong')
        advanceStage()
      }
    },

    skip: () => {
      const round = current()
      if (get().phase !== 'playing' || !round) return
      updateCurrent({ guesses: [...round.guesses, { songId: '', label: 'Пропуск', stage: round.stage, sameArtist: false, skipped: true }] })
      advanceStage()
    },

    hint: () => {
      const round = current()
      if (get().phase !== 'playing' || !round || round.hints >= MAX_HINTS) return
      updateCurrent({ hints: round.hints + 1 })
    },

    next: async () => {
      audio.stop()
      if (isOver()) get().finish()
      else await loadNextRound()
    },

    finish: () => {
      const { config, rounds, score, bestStreak } = get()
      audio.stop()
      session++
      set({ phase: 'finished' })
      if (!config || config.mode === 'practice') return
      const done = rounds.filter((r) => r.status !== 'playing')
      if (!done.length) return
      const unlocked = useStats.getState().recordGame(
        {
          id: `${Date.now()}`,
          mode: config.mode,
          difficulty: config.difficulty,
          date: Date.now(),
          score,
          correct: done.filter((r) => r.status === 'won').length,
          total: done.length,
          bestStreak,
          dailyKey: config.dailyKey,
          rounds: done.map((r) => ({
            songId: r.song.id,
            label: `${r.song.artist} — ${r.song.title}`,
            stage: r.status === 'won' ? r.stage : null,
            points: r.points
          }))
        },
        done
      )
      notifyAchievements(unlocked)
    },

    quit: () => {
      session++
      audio.stop()
      prefetched.clear()
      set({ phase: 'idle', config: null, rounds: [], buffer: null })
      useUi.getState().go('home')
    }
  }
})
