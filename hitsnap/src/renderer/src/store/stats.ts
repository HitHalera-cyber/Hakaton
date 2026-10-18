import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ACHIEVEMENTS, wonDecade, type AchievementContext } from '@/lib/achievements'
import type { Difficulty, GameMode, Round } from '@/lib/game'
import { diskStorage } from './persist'

export interface GameRecord {
  id: string
  mode: GameMode
  difficulty: Difficulty
  date: number
  score: number
  correct: number
  total: number
  bestStreak: number
  dailyKey?: string
  rounds: Array<{ songId: string; label: string; stage: number | null; points: number }>
}

export interface SongStat {
  played: number
  won: number
  best: number | null // best stage index
}

interface StatsData {
  totals: { games: number; rounds: number; wins: number; hints: number; guessMs: number }
  /** Wins per stage (index 0..2) plus losses at index 3. */
  stageHist: [number, number, number, number]
  bestStreak: number
  bestScore: Partial<Record<GameMode, number>>
  history: GameRecord[]
  songs: Record<string, SongStat>
  recent: string[]
  langsWon: string[]
  decadeWins: Record<string, number>
  daily: Record<string, { score: number; correct: number; total: number }>
  achievements: Record<string, number>
}

interface StatsStore extends StatsData {
  recordRound: (round: Round, scored: boolean) => string[]
  recordGame: (record: GameRecord, rounds: Round[]) => string[]
  noteStreak: (streak: number) => void
  reset: () => void
}

const EMPTY: StatsData = {
  totals: { games: 0, rounds: 0, wins: 0, hints: 0, guessMs: 0 },
  stageHist: [0, 0, 0, 0],
  bestStreak: 0,
  bestScore: {},
  history: [],
  songs: {},
  recent: [],
  langsWon: [],
  decadeWins: {},
  daily: {},
  achievements: {}
}

function context(s: StatsData, game?: AchievementContext['game']): AchievementContext {
  return {
    totals: { wins: s.totals.wins, rounds: s.totals.rounds, games: s.totals.games, firstStage: s.stageHist[0] },
    bestStreak: s.bestStreak,
    langsWon: s.langsWon,
    decadeWins: s.decadeWins,
    dailyDone: Object.keys(s.daily).length,
    game
  }
}

export const useStats = create<StatsStore>()(
  persist(
    (set, get) => {
      /** Unlocks whatever the new state qualifies for; returns the new ids. */
      const unlock = (game?: AchievementContext['game']): string[] => {
        const s = get()
        const ctx = context(s, game)
        const fresh = ACHIEVEMENTS.filter((a) => !s.achievements[a.id] && a.test(ctx)).map((a) => a.id)
        if (fresh.length) {
          const now = Date.now()
          set({ achievements: { ...s.achievements, ...Object.fromEntries(fresh.map((id) => [id, now])) } })
        }
        return fresh
      }

      return {
        ...EMPTY,
        recordRound: (round, scored) => {
          const s = get()
          const win = round.status === 'won'
          const prev = s.songs[round.song.id] ?? { played: 0, won: 0, best: null }
          const best = win ? (prev.best === null ? round.stage : Math.min(prev.best, round.stage)) : prev.best
          const recent = [round.song.id, ...s.recent.filter((id) => id !== round.song.id)].slice(0, 120)
          const songs = { ...s.songs, [round.song.id]: { played: prev.played + 1, won: prev.won + (win ? 1 : 0), best } }
          if (!scored) {
            set({ songs, recent })
            return []
          }
          const stageHist = [...s.stageHist] as StatsData['stageHist']
          stageHist[win ? round.stage : 3]++
          const decade = wonDecade(round)
          set({
            songs,
            recent,
            stageHist,
            totals: {
              ...s.totals,
              rounds: s.totals.rounds + 1,
              wins: s.totals.wins + (win ? 1 : 0),
              hints: s.totals.hints + round.hints,
              guessMs: s.totals.guessMs + (win && round.endedAt ? round.endedAt - round.startedAt : 0)
            },
            langsWon: win && !s.langsWon.includes(round.song.lang) ? [...s.langsWon, round.song.lang] : s.langsWon,
            decadeWins: win ? { ...s.decadeWins, [decade]: (s.decadeWins[decade] ?? 0) + 1 } : s.decadeWins
          })
          return unlock()
        },
        noteStreak: (streak) => {
          if (streak > get().bestStreak) set({ bestStreak: streak })
        },
        recordGame: (record, rounds) => {
          const s = get()
          const daily =
            record.mode === 'daily' && record.dailyKey && !s.daily[record.dailyKey]
              ? { ...s.daily, [record.dailyKey]: { score: record.score, correct: record.correct, total: record.total } }
              : s.daily
          set({
            totals: { ...s.totals, games: s.totals.games + 1 },
            bestScore: { ...s.bestScore, [record.mode]: Math.max(s.bestScore[record.mode] ?? 0, record.score) },
            bestStreak: Math.max(s.bestStreak, record.bestStreak),
            history: [record, ...s.history].slice(0, 200),
            daily
          })
          return unlock({ mode: record.mode, score: record.score, rounds })
        },
        reset: () => set({ ...EMPTY })
      }
    },
    { name: 'stats', storage: diskStorage, version: 1 }
  )
)
