import { create } from 'zustand'
import type { Song } from '@shared/types'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { api } from '@/lib/api'
import { audio, EFFECTS, leadingSilence } from '@/lib/audio'
import {
  answerFactor,
  answerKind,
  BLITZ_SECONDS,
  botStage,
  buildQueue,
  isCorrect,
  MAX_HINTS,
  pickOffset,
  pointsFor,
  quizOptions,
  sameArtist,
  STAGES,
  SURVIVAL_LIVES,
  YEAR_WIN_DISTANCE,
  yearCloseness,
  type GameConfig,
  type Round
} from '@/lib/game'
import { createRng } from '@/lib/random'
import { useSettings } from './settings'
import { useStats } from './stats'
import { useUi } from './ui'

// The game state machine:
//   loading → playing ⇄ (guess / skip / hint / buzz) → reveal → loading … → finished

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
  /** Songs the game is drawn from — also the source of quiz distractors. */
  pool: Song[]
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
  /** Party: points per player, who is answering now, who already missed this round. */
  partyScores: number[]
  buzzed: number | null
  lockedOut: number[]
  /** Blitz: milliseconds left on the clock. */
  blitzLeft: number
  /** Duel: the bot's points. */
  botScore: number
  start: (config: GameConfig, pool: Song[]) => Promise<void>
  playStage: () => void
  playReveal: () => void
  guess: (song: Song) => void
  guessYear: (year: number) => void
  guessArtist: (artist: string) => void
  /** Blitz: spend `ms` of the clock (only while a clip is being guessed). */
  tickBlitz: (ms: number) => void
  buzz: (player: number) => void
  skip: () => void
  hint: () => void
  next: () => Promise<void>
  finish: () => void
  quit: () => void
}

const MAX_FAILURES = 8

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

export function stagesOf(config: GameConfig): number[] {
  return STAGES[config.mode === 'daily' ? 'normal' : config.difficulty]
}

/** Points multiplier: answer type × sound effect. */
function factorOf(config: GameConfig): number {
  return answerFactor(answerKind(config.mode)) * EFFECTS[config.effect ?? 'none'].bonus
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
    const { config, rounds, lives, blitzLeft } = get()
    if (!config) return true
    if (config.mode === 'survival') return lives <= 0
    if (config.mode === 'blitz') return blitzLeft <= 0
    return rounds.length >= config.rounds
  }

  /** Where the clip starts: a random moment, or the very first sound. */
  const offsetFor = (buffer: AudioBuffer, config: GameConfig): number => {
    const stages = stagesOf(config)
    if (config.clipStart === 'intro') return leadingSilence(buffer)
    return pickOffset(buffer.duration, stages[stages.length - 1], rng)
  }

  /** Loads the next playable song, skipping ones without a preview. */
  const loadNextRound = async (): Promise<void> => {
    const id = session
    const { config } = get()
    if (!config) return
    set({ phase: 'loading', buffer: null, buzzed: null, lockedOut: [] })
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
            error: 'Не удаётся загрузить песни. Проверьте подключение к интернету — без сети доступны только уже прослушанные песни и своя музыка.'
          })
          return
        }
        continue
      }
      const round: Round = {
        song,
        offset: offsetFor(loaded.buffer, config),
        stage: 0,
        guesses: [],
        hints: 0,
        status: 'playing',
        points: 0,
        startedAt: Date.now(),
        coverUrl: loaded.coverUrl,
        link: loaded.link,
        album: loaded.album,
        options: answerKind(config.mode) === 'choice' ? quizOptions(song, get().pool, rng) : undefined,
        botStage: config.mode === 'duel' ? botStage(config.bot ?? 'mid', song.tier, rng) : undefined
      }
      set({ phase: 'playing', cursor, buffer: loaded.buffer, rounds: [...get().rounds, round] })
      if (queue[cursor]) void loadCached(queue[cursor])
      if (useSettings.getState().autoplay) get().playStage()
      return
    }
    set({ cursor })
    if (get().rounds.length) get().finish()
    else set({ phase: 'error', error: 'Под выбранные условия не нашлось ни одной песни. Ослабьте фильтры или выберите другую подборку.' })
  }

  const endRound = (won: boolean, points: number): void => {
    const { config, streak } = get()
    const round = current()
    if (!config || !round) return
    const scored = config.mode !== 'practice' && config.mode !== 'party'
    const newStreak = won ? streak + 1 : 0
    const lives = config.mode === 'survival' && !won ? get().lives - 1 : get().lives
    audio.stop()
    updateCurrent({ status: won ? 'won' : 'lost', points: scored ? points : 0, endedAt: Date.now() })
    const bot = config.mode === 'duel' && round.botStage != null ? pointsFor(round.botStage, 0, 0) : 0
    set({
      botScore: get().botScore + bot,
      phase: 'reveal',
      score: get().score + (scored ? points : 0),
      lastPoints: points,
      streak: newStreak,
      bestStreak: Math.max(get().bestStreak, newStreak),
      lives,
      buzzed: null
    })
    const finished = current()!
    const settings = useSettings.getState()
    if (settings.sfx) audio.sfx(won ? 'correct' : 'wrong')
    // Recognised from the very first clip — worth a celebration.
    if (won && finished.stage === 0 && answerKind(config.mode) !== 'year') useUi.getState().celebrate()
    // Let the answer cue sound, then keep the song playing from the clip start.
    setTimeout(() => {
      if (get().phase === 'reveal' && current() === finished) get().playReveal()
    }, settings.sfx ? 350 : 0)
    const stats = useStats.getState()
    const unlocked = stats.recordRound(finished, scored, { mode: config.mode, effect: config.effect ?? 'none', streak: newStreak })
    if (scored) stats.noteStreak(newStreak)
    notifyAchievements(unlocked)
    // Blitz keeps the pace: the next song comes by itself.
    if (config.mode === 'blitz') {
      setTimeout(() => {
        if (get().phase === 'reveal' && current() === finished) void get().next()
      }, won ? 1100 : 1600)
    }
  }

  const advanceStage = (): void => {
    const { config } = get()
    const round = current()
    if (!config || !round) return
    if (round.stage + 1 >= stagesOf(config).length) {
      endRound(false, 0)
      return
    }
    updateCurrent({ stage: round.stage + 1 })
    if (useSettings.getState().autoplay) setTimeout(() => get().phase === 'playing' && get().playStage(), 450)
  }

  return {
    phase: 'idle',
    config: null,
    pool: [],
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
    partyScores: [],
    buzzed: null,
    lockedOut: [],
    blitzLeft: 0,
    botScore: 0,

    start: async (config, pool) => {
      session++
      audio.stop()
      prefetched.clear()
      rng = createRng(config.seed ^ 0x9e3779b9)
      const recent = config.mode === 'daily' || config.weekKey || config.fixed ? [] : useStats.getState().recent
      let queue = buildQueue(pool, config, recent)
      // Offline: put songs that are already on disk (and own files) first.
      if (!navigator.onLine) {
        const cached = new Set((await api.cacheInfo()).songIds)
        const ready = (s: Song) => cached.has(s.id) || !!s.filePath
        queue = [...queue.filter(ready), ...queue.filter((s) => !ready(s))]
      }
      set({
        phase: 'loading',
        config,
        pool,
        queue,
        cursor: 0,
        rounds: [],
        buffer: null,
        score: 0,
        streak: 0,
        bestStreak: 0,
        lives: SURVIVAL_LIVES,
        lastPoints: 0,
        error: null,
        partyScores: (config.players ?? []).map(() => 0),
        buzzed: null,
        lockedOut: [],
        blitzLeft: BLITZ_SECONDS * 1000,
        botScore: 0
      })
      useUi.getState().go('game')
      await loadNextRound()
    },

    playStage: () => {
      const { buffer, config } = get()
      const round = current()
      if (!buffer || !config || !round) return
      audio.play(buffer, round.offset, stagesOf(config)[round.stage], config.effect ?? 'none')
    },

    playReveal: () => {
      const { buffer } = get()
      const round = current()
      if (!buffer || !round) return
      audio.play(buffer, round.offset)
    },

    guess: (song) => {
      const { config, buzzed, streak } = get()
      const round = current()
      if (get().phase !== 'playing' || !round || !config) return
      const party = config.mode === 'party'
      if (party && buzzed === null) return
      const correct = isCorrect(round.song, song)
      const guess = {
        songId: song.id,
        label: `${song.artist} — ${song.title}`,
        stage: round.stage,
        sameArtist: !correct && sameArtist(round.song, song),
        player: party ? buzzed! : undefined
      }
      updateCurrent({ guesses: [...round.guesses, guess] })
      if (correct) {
        if (party) {
          const partyScores = [...get().partyScores]
          const points = pointsFor(round.stage, 0, round.hints)
          partyScores[buzzed!] += points
          set({ partyScores })
          updateCurrent({ winner: buzzed! })
          endRound(true, points)
          return
        }
        endRound(true, pointsFor(round.stage, streak, round.hints, factorOf(config)))
        return
      }
      if (useSettings.getState().sfx) audio.sfx('wrong')
      if (party) {
        const lockedOut = [...get().lockedOut, buzzed!]
        set({ lockedOut, buzzed: null })
        if (lockedOut.length >= (config.players?.length ?? 0)) {
          endRound(false, 0)
          return
        }
      }
      advanceStage()
    },

    guessYear: (year) => {
      const { config, streak } = get()
      const round = current()
      if (get().phase !== 'playing' || !round || !config) return
      const closeness = yearCloseness(year, round.song.year)
      const won = Math.abs(year - round.song.year) <= YEAR_WIN_DISTANCE
      updateCurrent({ yearGuess: year })
      endRound(won, Math.round((pointsFor(round.stage, won ? streak : 0, round.hints, factorOf(config)) * closeness) / 10) * 10)
    },

    guessArtist: (artist) => {
      const { config, streak } = get()
      const round = current()
      if (get().phase !== 'playing' || !round || !config) return
      const pseudo = { ...round.song, id: `artist:${artist}`, artist }
      const correct = sameArtist(round.song, pseudo)
      updateCurrent({ guesses: [...round.guesses, { songId: pseudo.id, label: artist, stage: round.stage, sameArtist: false }] })
      if (correct) {
        endRound(true, pointsFor(round.stage, streak, round.hints, factorOf(config)))
        return
      }
      if (useSettings.getState().sfx) audio.sfx('wrong')
      advanceStage()
    },

    tickBlitz: (ms) => {
      const { config, phase, blitzLeft } = get()
      if (config?.mode !== 'blitz' || phase !== 'playing') return
      const left = Math.max(0, blitzLeft - ms)
      set({ blitzLeft: left })
      if (left === 0) {
        if (useSettings.getState().sfx) audio.sfx('wrong')
        get().finish()
      }
    },

    buzz: (player) => {
      const { config, buzzed, lockedOut, phase } = get()
      if (phase !== 'playing' || config?.mode !== 'party' || buzzed !== null) return
      if (player < 0 || player >= (config.players?.length ?? 0) || lockedOut.includes(player)) return
      audio.stop()
      if (useSettings.getState().sfx) audio.sfx('tick')
      set({ buzzed: player })
    },

    skip: () => {
      const round = current()
      if (get().phase !== 'playing' || !round) return
      updateCurrent({ guesses: [...round.guesses, { songId: '', label: 'Пропуск', stage: round.stage, sameArtist: false, skipped: true }] })
      set({ buzzed: null })
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
      const { config, rounds, score, bestStreak, partyScores } = get()
      audio.stop()
      session++
      set({ phase: 'finished' })
      if (!config || config.mode === 'practice') return
      const done = rounds.filter((r) => r.status !== 'playing')
      if (!done.length) return
      const perfect = done.length >= 5 && done.every((r) => r.status === 'won')
      if (perfect || (config.mode === 'duel' && done.length >= 3 && score > get().botScore)) setTimeout(() => useUi.getState().celebrate(), 300)
      const unlocked = useStats.getState().recordGame(
        {
          id: `${Date.now()}`,
          mode: config.mode,
          difficulty: config.difficulty,
          date: Date.now(),
          score: config.mode === 'party' ? Math.max(0, ...partyScores) : score,
          correct: done.filter((r) => r.status === 'won').length,
          total: done.length,
          bestStreak,
          dailyKey: config.dailyKey,
          weekKey: config.weekKey,
          label: config.source?.label,
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
      set({ phase: 'idle', config: null, rounds: [], buffer: null, pool: [] })
      useUi.getState().go('home')
    }
  }
})
