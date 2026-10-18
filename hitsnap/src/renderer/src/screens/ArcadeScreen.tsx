import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, ArrowLeft, ArrowUp, Check, RotateCcw, Trophy, X } from 'lucide-react'
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import type { Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { PreviewButton } from '@/components/PreviewButton'
import { Button, Card, cx } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { audio } from '@/lib/audio'
import { decadeOf, sameArtist } from '@/lib/game'
import { plural } from '@/lib/format'
import { ARCADE_INFO, type ArcadeGame } from '@/lib/quests'
import { shuffle } from '@/lib/random'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

// Игротека: quick music trivia without the clip ladder. Every game can play
// previews, but none needs them — they are about knowing the music.

const STYLE: Record<ArcadeGame, { from: string; to: string }> = {
  older: { from: '#f59e0b', to: '#db2777' },
  timeline: { from: '#0ea5e9', to: '#6366f1' },
  whose: { from: '#8b5cf6', to: '#ec4899' },
  odd: { from: '#16a34a', to: '#0d9488' }
}

/** Songs everyone has a chance with: known year, not too obscure. */
function usePool(): Song[] {
  const songs = useAllSongs()
  return useMemo(() => songs.filter((s) => s.year >= 1950 && s.tier <= 2), [songs])
}

function finish(game: ArcadeGame, score: number, xp: number): void {
  const ids = useStats.getState().recordArcade(game, score, xp)
  const { toast } = useUi.getState()
  if (xp > 0) toast({ title: `+${xp} опыта`, body: ARCADE_INFO[game].title, icon: ARCADE_INFO[game].emoji })
  for (const id of ids) {
    const a = ACHIEVEMENTS.find((x) => x.id === id)
    if (a) toast({ title: `Достижение: ${a.title}`, body: a.description, icon: a.icon, tone: 'success' })
  }
}

function cue(kind: 'correct' | 'wrong'): void {
  if (useSettings.getState().sfx) audio.sfx(kind)
}

export function ArcadeScreen() {
  const [game, setGame] = useState<ArcadeGame | null>(null)
  const best = useStats((s) => s.arcade)

  if (game) {
    return (
      <div className="mx-auto max-w-3xl">
        <button onClick={() => setGame(null)} className="mb-4 flex items-center gap-1.5 text-sm text-muted hover:text-fg cursor-pointer">
          <ArrowLeft size={16} /> Игротека
        </button>
        <div className="mb-6 flex items-center gap-3">
          <span className="text-4xl">{ARCADE_INFO[game].emoji}</span>
          <div>
            <h1 className="text-2xl font-black tracking-tight">{ARCADE_INFO[game].title}</h1>
            <p className="text-sm text-muted">{ARCADE_INFO[game].subtitle}</p>
          </div>
          {best[game] !== undefined && (
            <div className="ml-auto flex items-center gap-1.5 rounded-full bg-warn/15 px-3 py-1.5 text-sm font-semibold text-warn">
              <Trophy size={15} /> рекорд {best[game]}
            </div>
          )}
        </div>
        {game === 'older' && <OlderGame />}
        {game === 'timeline' && <TimelineGame />}
        {game === 'whose' && <WhoseGame />}
        {game === 'odd' && <OddGame />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-3xl font-black tracking-tight">Игротека</h1>
      <p className="mb-6 mt-1 text-muted">Мини-игры о музыке: годы, исполнители, хронология. Каждая приносит опыт.</p>
      <div className="grid gap-4 md:grid-cols-2">
        {(Object.keys(ARCADE_INFO) as ArcadeGame[]).map((g, i) => (
          <motion.button
            key={g}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ y: -4, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setGame(g)}
            className="relative h-44 overflow-hidden rounded-3xl p-6 text-left text-white shadow-xl cursor-pointer"
            style={{ background: `linear-gradient(135deg, ${STYLE[g].from}, ${STYLE[g].to})` }}
          >
            <span className="absolute -bottom-4 -right-2 text-8xl opacity-30">{ARCADE_INFO[g].emoji}</span>
            <span className="relative block text-2xl font-black">{ARCADE_INFO[g].title}</span>
            <span className="relative mt-1 block max-w-xs text-sm text-white/85">{ARCADE_INFO[g].subtitle}</span>
            <span className="absolute bottom-5 left-6 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold backdrop-blur">
              {best[g] !== undefined ? `Рекорд: ${best[g]}` : 'Ещё не играли'}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}

function SongTile({
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
        <PreviewButton song={song} preview={preview} />
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
function tone(state: 'good' | 'bad' | null | undefined): string {
  if (state === 'good') return 'border-good/60 bg-good/15 ring-2 ring-good/30'
  if (state === 'bad') return 'border-bad/60 bg-bad/10 ring-2 ring-bad/25'
  return 'border-line bg-surface'
}

function GameOver({ title, detail, onAgain }: { title: string; detail: string; onAgain: () => void }) {
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

// ——— Что старше? ———

function OlderGame() {
  const pool = usePool()
  const preview = usePreview()
  const pickOther = useCallback(
    (than: Song): Song => {
      for (let i = 0; i < 50; i++) {
        const s = pool[Math.floor(Math.random() * pool.length)]
        if (s.year !== than.year && s.id !== than.id && Math.abs(s.year - than.year) <= 25) return s
      }
      return pool.find((s) => s.year !== than.year)!
    },
    [pool]
  )
  const fresh = useCallback(() => {
    const a = pool[Math.floor(Math.random() * pool.length)]
    return [a, pickOther(a)] as [Song, Song]
  }, [pool, pickOther])

  const [pair, setPair] = useState<[Song, Song]>(fresh)
  const [picked, setPicked] = useState<0 | 1 | null>(null)
  const [streak, setStreak] = useState(0)
  const [over, setOver] = useState(false)

  const choose = (i: 0 | 1) => {
    if (picked !== null || over) return
    setPicked(i)
    const older = pair[0].year < pair[1].year ? 0 : 1
    if (i === older) {
      cue('correct')
      const next = streak + 1
      setStreak(next)
      setTimeout(() => {
        // The newer card stays and gets a new rival: the chain goes on.
        const keep = pair[i === 0 ? 1 : 0]
        setPair([keep, pickOther(keep)])
        setPicked(null)
      }, 1100)
    } else {
      cue('wrong')
      setOver(true)
      finish('older', streak, streak * 50)
    }
  }

  const again = () => {
    setPair(fresh())
    setPicked(null)
    setStreak(0)
    setOver(false)
  }

  const older = pair[0].year < pair[1].year ? 0 : 1
  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div className="text-lg font-semibold">Какая песня вышла раньше?</div>
        <div className="rounded-full bg-accent/15 px-3 py-1 text-sm font-bold text-accent">серия {streak}</div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {pair.map((song, i) => (
          <SongTile
            key={song.id}
            song={song}
            preview={preview}
            onClick={() => choose(i as 0 | 1)}
            disabled={picked !== null || over}
            showYear={picked !== null}
            state={picked === null ? null : i === older ? 'good' : picked === i ? 'bad' : null}
          />
        ))}
      </div>
      {over && <GameOver title={`Серия: ${streak}`} detail={`+${streak * 50} опыта. Каждая верная пара продлевает цепочку.`} onAgain={again} />}
    </>
  )
}

// ——— Хронология ———

function TimelineGame() {
  const pool = usePool()
  const preview = usePreview()
  const deal = useCallback(() => {
    const picked: Song[] = []
    const years = new Set<number>()
    for (const s of shuffle(pool)) {
      if (years.has(s.year)) continue
      years.add(s.year)
      picked.push(s)
      if (picked.length === 5) break
    }
    return picked
  }, [pool])

  const [order, setOrder] = useState<Song[]>(deal)
  const [checked, setChecked] = useState(false)
  const sorted = useMemo(() => [...order].sort((a, b) => a.year - b.year), [order])
  const correct = order.filter((s, i) => sorted[i].id === s.id).length

  const move = (i: number, d: -1 | 1) => {
    const j = i + d
    if (checked || j < 0 || j >= order.length) return
    const next = [...order]
    ;[next[i], next[j]] = [next[j], next[i]]
    setOrder(next)
  }

  const check = () => {
    setChecked(true)
    cue(correct >= 4 ? 'correct' : 'wrong')
    finish('timeline', correct, correct * 80)
  }

  return (
    <>
      <div className="mb-4 text-lg font-semibold">Сверху — самая старая, снизу — самая новая</div>
      <div className="space-y-2">
        {order.map((song, i) => {
          const ok = checked && sorted[i].id === song.id
          return (
            <motion.div
              layout
              key={song.id}
              className={cx('flex items-center gap-3 rounded-2xl border p-3 backdrop-blur-xl', tone(checked ? (ok ? 'good' : 'bad') : null))}
            >
              <span className="w-6 text-center text-lg font-black text-muted">{i + 1}</span>
              <Cover song={song} className="h-12 w-12 rounded-xl" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{song.title}</div>
                <div className="truncate text-sm text-muted">{song.artist}</div>
              </div>
              {checked ? (
                <span className="flex items-center gap-2 text-lg font-black tabular-nums">
                  {ok ? <Check size={18} className="text-good" /> : <X size={18} className="text-bad" />}
                  {song.year}
                </span>
              ) : (
                <>
                  <PreviewButton song={song} preview={preview} />
                  <div className="flex flex-col">
                    <button onClick={() => move(i, -1)} disabled={i === 0} className="rounded-md p-1 text-muted hover:bg-fg/5 hover:text-fg disabled:opacity-20 cursor-pointer" aria-label="Выше">
                      <ArrowUp size={16} />
                    </button>
                    <button onClick={() => move(i, 1)} disabled={i === order.length - 1} className="rounded-md p-1 text-muted hover:bg-fg/5 hover:text-fg disabled:opacity-20 cursor-pointer" aria-label="Ниже">
                      <ArrowDown size={16} />
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          )
        })}
      </div>
      {!checked ? (
        <Button variant="primary" size="lg" className="mt-5 w-full" onClick={check}>
          <Check size={18} /> Проверить
        </Button>
      ) : (
        <GameOver
          title={correct === 5 ? 'Идеально! Все на своих местах' : `На своих местах: ${correct} из 5`}
          detail={`+${correct * 80} опыта`}
          onAgain={() => {
            setOrder(deal())
            setChecked(false)
          }}
        />
      )}
    </>
  )
}

// ——— Quiz-style games: «Чья песня?» and «Найди лишнее» ———

const QUESTIONS = 10

interface Question {
  /** What is shown: titles for «Чья песня?», songs for «Найди лишнее». */
  songs: Song[]
  options: string[]
  answer: string
}

function useQuiz(make: () => Question | null, game: ArcadeGame, xpPer: number) {
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

function OptionButton({ label, state, onClick, sub }: { label: string; state: 'good' | 'bad' | null; onClick: () => void; sub?: string }) {
  return (
    <motion.button
      whileHover={state ? undefined : { y: -2 }}
      onClick={onClick}
      className={cx(
        'w-full rounded-2xl border p-4 pr-14 text-left font-semibold backdrop-blur-xl transition cursor-pointer',
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

function QuizFrame({ n, score, children }: { n: number; score: number; children: ReactNode }) {
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

function WhoseGame() {
  const pool = usePool()
  const byArtist = useMemo(() => {
    const m = new Map<string, Song[]>()
    for (const s of pool) {
      const list = m.get(s.artist) ?? []
      list.push(s)
      m.set(s.artist, list)
    }
    return [...m.entries()].filter(([, songs]) => songs.length >= 3)
  }, [pool])

  const make = useCallback((): Question | null => {
    if (byArtist.length < 4) return null
    const [artist, songs] = byArtist[Math.floor(Math.random() * byArtist.length)]
    const genre = songs[0].genre
    const others = shuffle(byArtist.filter(([a, s]) => a !== artist && !sameArtist(s[0], songs[0])))
    const similar = others.filter(([, s]) => s[0].genre === genre)
    const wrong = [...similar, ...others].map(([a]) => a).filter((a, i, all) => all.indexOf(a) === i).slice(0, 3)
    return { songs: shuffle(songs).slice(0, 3), options: shuffle([artist, ...wrong]), answer: artist }
  }, [byArtist])

  const { q, n, score, picked, over, pick, again } = useQuiz(make, 'whose', 60)
  if (!q) return <Card className="p-6 text-muted">Недостаточно песен для этой игры.</Card>
  return (
    <QuizFrame n={n} score={score}>
      <Card className="mb-4 p-6">
        <div className="mb-3 text-sm text-muted">У этого исполнителя есть песни:</div>
        <div className="space-y-2">
          {q.songs.map((s) => (
            <div key={s.id} className="text-xl font-bold">
              «{s.title}» <span className="text-sm font-normal text-muted">· {s.year}</span>
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-3">
        {q.options.map((o) => (
          <OptionButton key={o} label={o} onClick={() => pick(o)} state={!picked ? null : o === q.answer ? 'good' : o === picked ? 'bad' : null} />
        ))}
      </div>
      {over && <GameOver title={`Верно: ${score} из ${QUESTIONS}`} detail={`+${score * 60} опыта`} onAgain={again} />}
    </QuizFrame>
  )
}

function OddGame() {
  const pool = usePool()
  const preview = usePreview()
  const byDecade = useMemo(() => {
    const m = new Map<number, Song[]>()
    for (const s of pool) {
      const d = decadeOf(s.year)
      m.set(d, [...(m.get(d) ?? []), s])
    }
    return m
  }, [pool])

  const make = useCallback((): Question | null => {
    const decades = [...byDecade.keys()].filter((d) => (byDecade.get(d)?.length ?? 0) >= 3)
    if (decades.length < 2) return null
    const d = decades[Math.floor(Math.random() * decades.length)]
    const far = decades.filter((x) => Math.abs(x - d) >= 20)
    const candidates = far.length ? far : decades.filter((x) => x !== d)
    const oddDecade = candidates[Math.floor(Math.random() * candidates.length)]
    const three = shuffle(byDecade.get(d)!).slice(0, 3)
    const odd = shuffle(byDecade.get(oddDecade)!)[0]
    const songs = shuffle([...three, odd])
    return { songs, options: songs.map((s) => s.id), answer: odd.id }
  }, [byDecade])

  const { q, n, score, picked, over, pick, again } = useQuiz(make, 'odd', 60)
  if (!q) return <Card className="p-6 text-muted">Недостаточно песен для этой игры.</Card>
  return (
    <QuizFrame n={n} score={score}>
      <div className="mb-4 text-lg font-semibold">Три песни из одного десятилетия. Какая — из другого?</div>
      <div className="grid grid-cols-2 gap-3">
        {q.songs.map((s) => (
          <div key={s.id} className="relative">
            <OptionButton
              label={s.title}
              sub={`${s.artist}${picked ? ` · ${s.year}` : ''}`}
              onClick={() => pick(s.id)}
              state={!picked ? null : s.id === q.answer ? 'good' : s.id === picked ? 'bad' : null}
            />
            <div className="absolute right-3 top-3">
              <PreviewButton song={s} preview={preview} />
            </div>
          </div>
        ))}
      </div>
      {over && <GameOver title={`Верно: ${score} из ${QUESTIONS}`} detail={`+${score * 60} опыта · ${plural(score, 'ответ', 'ответа', 'ответов')} в копилку`} onAgain={again} />}
    </QuizFrame>
  )
}
