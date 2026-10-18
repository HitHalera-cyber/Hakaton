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

// Игротека: quick music trivia without the clip ladder. Every song can be
// listened to before answering («Слушать»).

const STYLE: Record<ArcadeGame, { from: string; to: string }> = {
  older: { from: '#f59e0b', to: '#db2777' },
  timeline: { from: '#0ea5e9', to: '#6366f1' },
  whose: { from: '#8b5cf6', to: '#ec4899' },
  odd: { from: '#16a34a', to: '#0d9488' },
  cover: { from: '#f97316', to: '#be123c' },
  missing: { from: '#0891b2', to: '#4338ca' }
}

/** Songs everyone has a chance with: known year, not too obscure. */
function usePool(): Song[] {
  const songs = useAllSongs()
  return useMemo(() => songs.filter((s) => s.year >= 1950 && s.tier <= 2), [songs])
}

function finish(game: ArcadeGame, score: number, xp: number): void {
  const ids = useStats.getState().recordArcade(game, score, xp)
  const { toast, celebrate } = useUi.getState()
  const perfect = game === 'timeline' ? score === 5 : game === 'older' ? score >= 10 : game === 'cover' ? score >= 600 : score >= QUESTIONS
  if (perfect) celebrate()
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
        {game === 'cover' && <CoverGame />}
        {game === 'missing' && <MissingGame />}
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
    preview.stop()
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
    preview.stop()
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
                  <PreviewButton song={song} preview={preview} label />
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
  const preview = usePreview()
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
            <div key={s.id} className="flex items-center gap-3">
              <PreviewButton song={s} preview={preview} />
              <div className="text-xl font-bold">
                «{s.title}» <span className="text-sm font-normal text-muted">· {s.year}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-3">
        {q.options.map((o) => (
          <OptionButton
            key={o}
            label={o}
            onClick={() => {
              preview.stop()
              pick(o)
            }} state={!picked ? null : o === q.answer ? 'good' : o === picked ? 'bad' : null} />
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
          <div key={s.id} className="flex flex-col gap-2">
            <OptionButton
              label={s.title}
              sub={`${s.artist}${picked ? ` · ${s.year}` : ''}`}
              onClick={() => {
                preview.stop()
                pick(s.id)
              }}
              state={!picked ? null : s.id === q.answer ? 'good' : s.id === picked ? 'bad' : null}
            />
            <div className="flex justify-center">
              <PreviewButton song={s} preview={preview} label />
            </div>
          </div>
        ))}
      </div>
      {over && <GameOver title={`Верно: ${score} из ${QUESTIONS}`} detail={`+${score * 60} опыта · ${plural(score, 'ответ', 'ответа', 'ответов')} в копилку`} onAgain={again} />}
    </QuizFrame>
  )
}

// ——— По обложке ———

const COVER_ROUNDS = 8
/** Seconds until the cover is fully sharp. */
const COVER_SECONDS = 10

interface CoverQuestion {
  song: Song
  url?: string
  options: Song[]
}

function CoverGame() {
  const pool = usePool()
  const preview = usePreview()
  const rng = useMemo(() => createRng((Math.random() * 2 ** 32) >>> 0), [])

  /** A song with real album art (any song in the demo, which has none). */
  const makeQuestion = useCallback(async (): Promise<CoverQuestion | null> => {
    for (let i = 0; i < 6; i++) {
      const song = pool[Math.floor(Math.random() * pool.length)]
      const track = await api.resolveTrack(song).catch(() => null)
      if (!track) continue
      if (!track.coverUrl && i < 5 && !isDemo) continue
      return { song, url: track.coverUrl, options: quizOptions(song, pool, rng) }
    }
    return null
  }, [pool, rng])

  const [q, setQ] = useState<CoverQuestion | null>(null)
  const [n, setN] = useState(1)
  const [score, setScore] = useState(0)
  const [picked, setPicked] = useState<string | null>(null)
  const [over, setOver] = useState(false)
  const [failed, setFailed] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const upcoming = useRef<Promise<CoverQuestion | null> | null>(null)
  const startedAt = useRef(0)

  const load = useCallback(async () => {
    const pending = upcoming.current ?? makeQuestion()
    upcoming.current = null
    const next = await pending
    if (!next) {
      setFailed(true)
      return
    }
    setQ(next)
    setPicked(null)
    setElapsed(0)
    startedAt.current = performance.now()
    upcoming.current = makeQuestion()
  }, [makeQuestion])

  useEffect(() => {
    void load()
  }, [load])

  // The cover sharpens while nobody has answered.
  useEffect(() => {
    if (!q || picked || over) return
    const id = setInterval(() => setElapsed(Math.min(COVER_SECONDS, (performance.now() - startedAt.current) / 1000)), 100)
    return () => clearInterval(id)
  }, [q, picked, over])

  const points = Math.max(10, Math.round((COVER_SECONDS - elapsed) * 10))
  const pick = (song: Song) => {
    if (!q || picked || over) return
    preview.stop()
    setPicked(song.id)
    const ok = song.id === q.song.id
    cue(ok ? 'correct' : 'wrong')
    const total = score + (ok ? points : 0)
    setScore(total)
    setTimeout(() => {
      if (n >= COVER_ROUNDS) {
        setOver(true)
        finish('cover', total, Math.round(total / 2))
      } else {
        setN(n + 1)
        setQ(null)
        void load()
      }
    }, 1500)
  }
  const again = () => {
    setN(1)
    setScore(0)
    setOver(false)
    setQ(null)
    void load()
  }

  if (failed) return <Card className="p-6 text-muted">Не удалось загрузить обложки — проверьте подключение к интернету.</Card>
  const blur = picked ? 0 : 28 * (1 - elapsed / COVER_SECONDS)
  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-fg/10">
          <motion.div className="bg-gradient-accent h-full" animate={{ width: `${(n / COVER_ROUNDS) * 100}%` }} />
        </div>
        <span className="text-sm text-muted">
          {n}/{COVER_ROUNDS}
        </span>
        <span className="rounded-full bg-accent/15 px-3 py-1 text-sm font-bold text-accent">{score}</span>
      </div>
      {!q ? (
        <Card className="flex h-80 items-center justify-center text-muted">Ищем обложку…</Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-[280px_1fr]">
          <div>
            <div className="relative h-[280px] w-[280px] overflow-hidden rounded-3xl shadow-2xl">
              <div style={{ filter: `blur(${blur}px) saturate(${picked ? 1 : 1.3})`, transform: `scale(${1 + blur / 60})` }} className="transition-[filter] duration-100">
                <Cover song={q.song} url={q.url} className="h-[280px] w-[280px]" />
              </div>
              {!picked && (
                <div className="absolute bottom-3 right-3 rounded-full bg-black/50 px-3 py-1 text-sm font-bold text-white tabular-nums backdrop-blur">+{points}</div>
              )}
            </div>
            <div className="mt-3 flex justify-center">
              <PreviewButton song={q.song} preview={preview} label />
            </div>
          </div>
          <div className="grid content-start gap-2">
            {q.options.map((o) => (
              <OptionButton
                key={o.id}
                label={o.title}
                sub={o.artist}
                onClick={() => pick(o)}
                state={!picked ? null : o.id === q.song.id ? 'good' : o.id === picked ? 'bad' : null}
              />
            ))}
          </div>
        </div>
      )}
      {over && <GameOver title={`Очки: ${score}`} detail={`+${Math.round(score / 2)} опыта. Чем раньше узнаёте обложку, тем больше очков.`} onAgain={again} />}
    </>
  )
}

// ——— Допиши название ———

const WORD = /^[\p{L}'’]{4,}$/u

/** Splits a title into words, keeping the separators so it can be put back together. */
function titleWords(title: string): string[] {
  return title.split(/(\s+)/)
}

function MissingGame() {
  const pool = usePool()
  const preview = usePreview()
  const candidates = useMemo(
    () => pool.filter((s) => s.title.length <= 40 && !/[()[\]]/.test(s.title) && titleWords(s.title).filter((w) => WORD.test(w)).length >= 2),
    [pool]
  )
  const wordsByLang = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const s of candidates) for (const w of titleWords(s.title)) if (WORD.test(w)) m.set(s.lang, [...(m.get(s.lang) ?? []), w])
    return m
  }, [candidates])

  const make = useCallback((): Question | null => {
    if (candidates.length < 10) return null
    const song = candidates[Math.floor(Math.random() * candidates.length)]
    const words = titleWords(song.title)
    const slots = words.map((w, i) => (WORD.test(w) ? i : -1)).filter((i) => i >= 0)
    const slot = slots[Math.floor(Math.random() * slots.length)]
    const answer = words[slot]
    const norm = (w: string) => w.toLowerCase()
    const similar = shuffle(wordsByLang.get(song.lang) ?? []).filter((w) => norm(w) !== norm(answer) && Math.abs(w.length - answer.length) <= 3)
    const wrong = [...new Set(similar.map((w) => (answer[0] === answer[0].toUpperCase() ? w[0].toUpperCase() + w.slice(1) : w.toLowerCase())))].slice(0, 3)
    if (wrong.length < 3) return null
    const shown = words.map((w, i) => (i === slot ? '＿＿＿' : w)).join('')
    return { songs: [{ ...song, title: shown }, song], options: shuffle([answer, ...wrong]), answer }
  }, [candidates, wordsByLang])

  const makeSafe = useCallback((): Question | null => {
    for (let i = 0; i < 20; i++) {
      const q = make()
      if (q) return q
    }
    return null
  }, [make])

  const { q, n, score, picked, over, pick, again } = useQuiz(makeSafe, 'missing', 60)
  if (!q) return <Card className="p-6 text-muted">Недостаточно песен для этой игры.</Card>
  const [shown, song] = q.songs
  return (
    <QuizFrame n={n} score={score}>
      <Card className="mb-4 flex items-center gap-5 p-6">
        <Cover song={song} className="h-20 w-20 shrink-0 rounded-2xl" />
        <div className="min-w-0 flex-1">
          <div className="text-2xl font-black leading-tight">{picked ? song.title : shown.title}</div>
          <div className="mt-1 text-muted">
            {song.artist} · {song.year}
          </div>
        </div>
        <PreviewButton song={song} preview={preview} label />
      </Card>
      <div className="grid grid-cols-2 gap-3">
        {q.options.map((o) => (
          <OptionButton
            key={o}
            label={o}
            onClick={() => {
              preview.stop()
              pick(o)
            }}
            state={!picked ? null : o === q.answer ? 'good' : o === picked ? 'bad' : null}
          />
        ))}
      </div>
      {over && <GameOver title={`Верно: ${score} из ${QUESTIONS}`} detail={`+${score * 60} опыта`} onAgain={again} />}
    </QuizFrame>
  )
}
