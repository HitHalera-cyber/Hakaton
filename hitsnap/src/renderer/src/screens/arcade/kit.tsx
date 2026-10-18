import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, ArrowLeft, ArrowUp, Check, RotateCcw, Trophy, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { PreviewButton } from '@/components/PreviewButton'
import { Button, Card, cx } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { api, isDemo } from '@/lib/api'
import { audio } from '@/lib/audio'
import { createRng } from '@/lib/random'
import { decadeOf, quizOptions, sameArtist } from '@/lib/game'
import { plural } from '@/lib/format'
import { ARCADE_INFO, type ArcadeGame } from '@/lib/quests'
import { shuffle } from '@/lib/random'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

// Shared pieces of the Игротека games.

export function usePool(): Song[] {
  const songs = useAllSongs()
  return useMemo(() => songs.filter((s) => s.year >= 1950 && s.tier <= 2), [songs])
}

/** Records a finished game; `perfect` (worth confetti) defaults to each classic game's top result. */
export function finish(game: ArcadeGame, score: number, xp: number, perfect?: boolean): void {
  const ids = useStats.getState().recordArcade(game, score, xp)
  const { toast, celebrate } = useUi.getState()
  if (perfect ?? (game === 'timeline' ? score === 5 : game === 'older' ? score >= 10 : game === 'cover' ? score >= 600 : score >= QUESTIONS)) celebrate()
  if (xp > 0) toast({ title: `+${xp} опыта`, body: ARCADE_INFO[game].title, icon: ARCADE_INFO[game].emoji })
  for (const id of ids) {
    const a = ACHIEVEMENTS.find((x) => x.id === id)
    if (a) toast({ title: `Достижение: ${a.title}`, body: a.description, icon: a.icon, tone: 'success' })
  }
}

export function cue(kind: 'correct' | 'wrong'): void {
  if (useSettings.getState().sfx) audio.sfx(kind)
}

export function SongTile({
  song,
  preview,
  onClick,
  state,
  showYear,
  disabled
}: {
  song: Song
  preview: ReturnType<typeof usePreview>
  onClick?: () => void
  state?: 'good' | 'bad' | null
  showYear?: boolean
  disabled?: boolean
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cx(
        'relative flex flex-col items-center rounded-3xl border p-5 text-center backdrop-blur-xl transition',
        tone(state),
        onClick && !disabled && 'cursor-pointer hover:border-accent/60 hover:-translate-y-1'
      )}
      onClick={disabled ? undefined : onClick}
    >
      <Cover song={song} className="h-32 w-32 rounded-2xl shadow-xl" />
      <div className="mt-4 line-clamp-2 text-lg font-bold leading-tight">{song.title}</div>
      <div className="mt-1 text-sm text-muted">{song.artist}</div>
      <div className="mt-3 flex h-9 items-center gap-2" onClick={(e) => e.stopPropagation()}>
        <PreviewButton song={song} preview={preview} label />
        <AnimatePresence>
          {showYear && (
            <motion.span initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-gradient text-2xl font-black tabular-nums">
              {song.year}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

/** Card colours for neutral / right / wrong (instead of .glass, whose colours cannot be overridden). */
export function tone(state: 'good' | 'bad' | null | undefined): string {
  if (state === 'good') return 'border-good/60 bg-good/15 ring-2 ring-good/30'
  if (state === 'bad') return 'border-bad/60 bg-bad/10 ring-2 ring-bad/25'
  return 'border-line bg-surface'
}

export function GameOver({ title, detail, onAgain }: { title: string; detail: string; onAgain: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="mt-6 flex items-center gap-4 p-5">
        <div className="text-4xl">🏁</div>
        <div className="flex-1">
          <div className="text-lg font-bold">{title}</div>
          <div className="text-sm text-muted">{detail}</div>
        </div>
        <Button variant="primary" onClick={onAgain}>
          <RotateCcw size={16} /> Ещё раз
        </Button>
      </Card>
    </motion.div>
  )
}

// ——— Quiz-style games: «Чья песня?» and «Найди лишнее» ———

export const QUESTIONS = 10

export interface Question {
  /** What is shown: titles for «Чья песня?», songs for «Найди лишнее». */
  songs: Song[]
  options: string[]
  answer: string
}

export function useQuiz(make: () => Question | null, game: ArcadeGame, xpPer: number) {
  const [q, setQ] = useState<Question | null>(make)
  const [n, setN] = useState(1)
  const [score, setScore] = useState(0)
  const [picked, setPicked] = useState<string | null>(null)
  const [over, setOver] = useState(false)

  const pick = (option: string) => {
    if (picked || over || !q) return
    setPicked(option)
    const ok = option === q.answer
    cue(ok ? 'correct' : 'wrong')
    const total = score + (ok ? 1 : 0)
    setScore(total)
    setTimeout(() => {
      if (n >= QUESTIONS) {
        setOver(true)
        finish(game, total, total * xpPer)
      } else {
        setN(n + 1)
        setQ(make())
        setPicked(null)
      }
    }, 1300)
  }
  const again = () => {
    setQ(make())
    setN(1)
    setScore(0)
    setPicked(null)
    setOver(false)
  }
  return { q, n, score, picked, over, pick, again }
}

export function OptionButton({ label, state, onClick, sub }: { label: string; state: 'good' | 'bad' | null; onClick: () => void; sub?: string }) {
  return (
    <motion.button
      whileHover={state ? undefined : { y: -2 }}
      onClick={onClick}
      className={cx(
        'w-full rounded-2xl border p-4 text-left font-semibold backdrop-blur-xl transition cursor-pointer',
        tone(state),
        state === 'good' && 'text-good',
        state === 'bad' && 'text-bad',
        !state && 'hover:border-accent/60'
      )}
    >
      {label}
      {sub && <span className="mt-0.5 block text-xs font-normal text-muted">{sub}</span>}
    </motion.button>
  )
}

export function QuizFrame({ n, score, children }: { n: number; score: number; children: ReactNode }) {
  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-fg/10">
          <motion.div className="bg-gradient-accent h-full" animate={{ width: `${(n / QUESTIONS) * 100}%` }} />
        </div>
        <span className="text-sm text-muted">
          {n}/{QUESTIONS}
        </span>
        <span className="rounded-full bg-accent/15 px-3 py-1 text-sm font-bold text-accent">{score}</span>
      </div>
      {children}
    </>
  )
}
