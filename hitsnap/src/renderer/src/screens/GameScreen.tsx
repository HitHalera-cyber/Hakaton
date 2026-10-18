import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowRight,
  Check,
  ExternalLink,
  Flag,
  Flame,
  Heart,
  Home,
  Lightbulb,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
  Users,
  X
} from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Cover } from '@/components/Cover'
import { SearchBox, type SearchBoxHandle } from '@/components/SearchBox'
import { StageTimeline } from '@/components/StageTimeline'
import { Button, Card, cx, Kbd } from '@/components/ui'
import { Visualizer } from '@/components/Visualizer'
import { usePlayback } from '@/hooks/usePlayback'
import { audio } from '@/lib/audio'
import { formatNumber, formatSeconds, plural } from '@/lib/format'
import { hintsFor, MAX_HINTS, MODE_INFO, seedFor, STAGES, streakMultiplier, SURVIVAL_LIVES, type Round } from '@/lib/game'
import { api } from '@/lib/api'
import { useGame } from '@/store/game'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { CATALOG } from '@shared/catalog'

export function GameScreen() {
  const phase = useGame((s) => s.phase)
  if (phase === 'finished') return <Results />
  if (phase === 'error') return <ErrorView />
  if (phase === 'idle') return <Idle />
  return <Board />
}

function Idle() {
  const quit = useGame((s) => s.quit)
  useEffect(() => quit(), [quit])
  return null
}

function useStages(): number[] {
  const config = useGame((s) => s.config)
  return STAGES[config?.mode === 'daily' ? 'normal' : (config?.difficulty ?? 'normal')]
}

function Header() {
  const { config, rounds, score, streak, lives, finish } = useGame()
  if (!config) return null
  const roundNo = rounds.length
  return (
    <div className="mb-6 flex items-center gap-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-muted">{MODE_INFO[config.mode].title}</div>
        <div className="text-xl font-bold">
          {config.mode === 'survival' || config.mode === 'practice' ? `Песня ${roundNo || 1}` : `Раунд ${roundNo || 1} из ${config.rounds}`}
        </div>
      </div>
      {config.mode === 'survival' && (
        <div className="ml-2 flex gap-1" title="Жизни">
          {Array.from({ length: SURVIVAL_LIVES }, (_, i) => (
            <motion.span key={i} animate={{ scale: i < lives ? 1 : 0.8, opacity: i < lives ? 1 : 0.25 }}>
              <Heart size={20} className="text-bad" fill="currentColor" />
            </motion.span>
          ))}
        </div>
      )}
      <div className="ml-auto flex items-center gap-3">
        <AnimatePresence>
          {streak >= 2 && config.mode !== 'practice' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.6 }}
              className="flex items-center gap-1.5 rounded-full bg-warn/15 px-3 py-1.5 text-sm font-semibold text-warn"
              title="Серия угаданных подряд: бонус к очкам"
            >
              <Flame size={16} /> {streak} · ×{streakMultiplier(streak).toFixed(1)}
            </motion.div>
          )}
        </AnimatePresence>
        {config.mode !== 'practice' && (
          <div className="glass rounded-xl px-4 py-1.5 text-right">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">Очки</div>
            <motion.div key={score} initial={{ scale: 1.25 }} animate={{ scale: 1 }} className="text-lg font-bold tabular-nums">
              {formatNumber(score)}
            </motion.div>
          </div>
        )}
        <Button variant="ghost" onClick={finish} title="Завершить игру и посмотреть итоги">
          <Flag size={16} /> Завершить
        </Button>
      </div>
    </div>
  )
}

function Board() {
  const { phase, rounds, playStage, playReveal, guess, skip, hint, next } = useGame()
  const visualizer = useSettings((s) => s.visualizer)
  const stages = useStages()
  const playback = usePlayback()
  const searchRef = useRef<SearchBoxHandle>(null)
  const round: Round | undefined = rounds[rounds.length - 1]
  const playing = phase === 'playing'
  const reveal = phase === 'reveal'

  useEffect(() => {
    if (playing) searchRef.current?.focus()
  }, [playing, round?.song.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement && e.target.value !== ''
      if (reveal && e.key === 'Enter') {
        e.preventDefault()
        void next()
      } else if (reveal && e.code === 'Space') {
        e.preventDefault()
        if (audio.state().playing) audio.stop()
        else playReveal()
      } else if (playing && e.code === 'Space' && !typing) {
        e.preventDefault()
        playStage()
      } else if (playing && e.key === 'Escape' && !typing) {
        e.preventDefault()
        skip()
      } else if (playing && e.ctrlKey && e.code === 'KeyH') {
        e.preventDefault()
        hint()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, reveal, next, playReveal, playStage, skip, hint])

  return (
    <div className="mx-auto max-w-3xl">
      <Header />
      {phase === 'loading' || !round ? (
        <Loading />
      ) : (
        <>
          <Card className="relative overflow-hidden p-6">
            <div className="flex items-center gap-6">
              <PlayDisc
                playing={playback.playing}
                onClick={() => (playback.playing ? audio.stop() : reveal ? playReveal() : playStage())}
                progress={playback.playing ? playback.elapsed / Math.max(playback.length, 0.01) : 0}
              />
              <div className="min-w-0 flex-1">
                {visualizer && <Visualizer className="mb-4 h-20 w-full" />}
                {!reveal && (
                  <StageTimeline stages={stages} stage={round.stage} elapsed={playback.elapsed} playing={playback.playing} />
                )}
                {reveal && (
                  <div className="text-sm text-muted">
                    {playback.playing ? 'Звучит превью песни…' : 'Нажмите ▶, чтобы послушать ещё раз'}
                  </div>
                )}
              </div>
            </div>
            {playing && (
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={playStage}>
                  <RotateCcw size={16} /> Повторить {formatSeconds(stages[round.stage])}
                </Button>
                <Button variant="secondary" onClick={skip}>
                  <SkipForward size={16} />
                  {round.stage + 1 < stages.length ? `Дальше: ${formatSeconds(stages[round.stage + 1])}` : 'Сдаться'}
                </Button>
                <Button variant="ghost" onClick={hint} disabled={round.hints >= MAX_HINTS}>
                  <Lightbulb size={16} /> Подсказка ({MAX_HINTS - round.hints})
                </Button>
                <div className="ml-auto hidden items-center gap-3 text-xs text-muted md:flex">
                  <span>
                    <Kbd>Пробел</Kbd> повтор
                  </span>
                  <span>
                    <Kbd>Esc</Kbd> дальше
                  </span>
                </div>
              </div>
            )}
          </Card>

          <AnimatePresence mode="wait">
            {playing ? (
              <motion.div key="guess" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5 space-y-4">
                <SearchBox
                  ref={searchRef}
                  onPick={guess}
                  excludeIds={round.guesses.map((g) => g.songId)}
                  placeholder="Что это за песня? Начните вводить название или исполнителя…"
                />
                <HintsAndGuesses round={round} />
              </motion.div>
            ) : (
              <motion.div key="reveal" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <RevealCard round={round} stages={stages} />
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  )
}

function PlayDisc({ playing, onClick, progress }: { playing: boolean; onClick: () => void; progress: number }) {
  const r = 46
  const c = 2 * Math.PI * r
  return (
    <button onClick={onClick} className="group relative h-28 w-28 shrink-0 cursor-pointer" aria-label={playing ? 'Стоп' : 'Слушать'}>
      <svg viewBox="0 0 100 100" className="absolute inset-0 -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="currentColor" strokeWidth="3" className="text-fg/10" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - progress)}
        />
      </svg>
      <span
        className={cx(
          'bg-gradient-accent absolute inset-2.5 flex items-center justify-center rounded-full text-white shadow-xl shadow-accent/40 transition group-hover:scale-105 group-active:scale-95',
          playing && 'spin-slow'
        )}
      >
        <span className="absolute inset-[30%] rounded-full border border-white/25" />
        <span className={cx(playing && '[animation:spin-slow_6s_linear_infinite_reverse]')}>
          {playing ? <Pause size={34} fill="currentColor" /> : <Play size={34} fill="currentColor" className="ml-1" />}
        </span>
      </span>
    </button>
  )
}

function HintsAndGuesses({ round }: { round: Round }) {
  const hints = hintsFor(round.song).slice(0, round.hints)
  if (!hints.length && !round.guesses.length) {
    return <p className="px-1 text-sm text-muted">Неверный ответ открывает отрывок подлиннее, но приносит меньше очков.</p>
  }
  return (
    <div className="space-y-2">
      <AnimatePresence>
        {hints.map((h) => (
          <motion.div
            key={h.label}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 rounded-xl border border-warn/30 bg-warn/10 px-4 py-2.5 text-sm"
          >
            <Lightbulb size={16} className="text-warn" />
            <span className="text-muted">{h.label}:</span>
            <span className="font-semibold">{h.value}</span>
          </motion.div>
        ))}
        {round.guesses.map((g, i) => (
          <motion.div
            key={`${g.songId}-${i}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-sm"
          >
            {g.skipped ? <SkipForward size={16} className="text-muted" /> : <X size={16} className="text-bad" />}
            <span className={cx(g.skipped ? 'text-muted' : 'line-through decoration-bad/60')}>{g.label}</span>
            {g.sameArtist && (
              <span className="ml-auto flex items-center gap-1 rounded-full bg-good/15 px-2 py-0.5 text-xs font-medium text-good">
                <Users size={12} /> исполнитель верный!
              </span>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

function RevealCard({ round, stages }: { round: Round; stages: number[] }) {
  const { next, config, lives } = useGame()
  const won = round.status === 'won'
  const lastRound = config && (config.mode === 'survival' ? lives <= 0 : useGame.getState().rounds.length >= config.rounds)
  return (
    <Card className="mt-5 overflow-hidden">
      <div className={cx('px-6 py-3 text-sm font-semibold', won ? 'bg-good/15 text-good' : 'bg-bad/10 text-bad')}>
        {won ? (
          <span className="flex items-center gap-2">
            <Check size={16} /> Угадано за {formatSeconds(stages[round.stage])}
            {round.points > 0 && <span className="ml-auto text-base">+{formatNumber(round.points)}</span>}
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <X size={16} /> Не угадано — это была…
            {config?.mode === 'survival' && <span className="ml-auto">−1 жизнь</span>}
          </span>
        )}
      </div>
      <div className="flex items-center gap-6 p-6">
        <motion.div initial={{ rotate: -8, scale: 0.8 }} animate={{ rotate: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 200 }}>
          <Cover song={round.song} url={round.coverUrl} className="h-36 w-36 rounded-2xl shadow-2xl" />
        </motion.div>
        <div className="min-w-0 flex-1">
          <div className="text-2xl font-bold leading-tight">{round.song.title}</div>
          <div className="mt-1 text-lg text-muted">{round.song.artist}</div>
          <div className="mt-2 text-sm text-muted">
            {[round.song.year > 0 && round.song.year, round.album].filter(Boolean).join(' · ')}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button variant="primary" size="lg" onClick={() => void next()} autoFocus>
              {lastRound ? 'К итогам' : 'Следующая'} <ArrowRight size={18} />
            </Button>
            {round.link && (
              <Button variant="ghost" onClick={() => void api.openExternal(round.link!)}>
                <ExternalLink size={16} /> Слушать целиком
              </Button>
            )}
          </div>
          <div className="mt-3 text-xs text-muted">
            <Kbd>Enter</Kbd> дальше · <Kbd>Пробел</Kbd> пауза / слушать
          </div>
        </div>
      </div>
    </Card>
  )
}

function Loading() {
  return (
    <Card className="flex flex-col items-center justify-center gap-4 p-16 text-muted">
      <div className="relative h-20 w-20">
        <div className="bg-gradient-accent spin-slow absolute inset-0 rounded-full opacity-80" />
        <div className="absolute inset-[38%] rounded-full bg-bg" />
      </div>
      <div className="flex items-center gap-2 text-sm">
        <Loader2 size={16} className="animate-spin" /> Подбираем песню…
      </div>
    </Card>
  )
}

function ErrorView() {
  const { error, config, start, quit } = useGame()
  const songs = useAllSongs()
  return (
    <div className="mx-auto mt-16 max-w-lg text-center">
      <div className="mb-4 text-5xl">🎧</div>
      <h2 className="text-xl font-bold">Не получилось начать игру</h2>
      <p className="mt-2 text-muted">{error}</p>
      <div className="mt-6 flex justify-center gap-3">
        {config && (
          <Button variant="primary" onClick={() => void start({ ...config, seed: seedFor(config.mode, config.dailyKey) }, config.mode === 'daily' ? CATALOG : songs)}>
            <RotateCcw size={16} /> Попробовать снова
          </Button>
        )}
        <Button onClick={quit}>
          <Home size={16} /> В меню
        </Button>
      </div>
    </div>
  )
}

function Results() {
  const { rounds, score, bestStreak, config, start, quit } = useGame()
  const songs = useAllSongs()
  const done = rounds.filter((r) => r.status !== 'playing')
  const correct = done.filter((r) => r.status === 'won').length
  const accuracy = done.length ? Math.round((correct / done.length) * 100) : 0
  const hist = [0, 1, 2].map((stage) => done.filter((r) => r.status === 'won' && r.stage === stage).length)
  const lost = done.length - correct
  const stages = useStages()
  const max = Math.max(1, ...hist, lost)
  const grade = accuracy >= 90 ? 'Легенда! 🎸' : accuracy >= 70 ? 'Меломан 🎧' : accuracy >= 40 ? 'Неплохо 🎶' : 'Есть куда расти 🎵'

  const again = () => {
    if (!config) return
    void start({ ...config, seed: seedFor(config.mode, config.dailyKey) }, config.mode === 'daily' ? CATALOG : songs)
  }

  return (
    <div className="mx-auto max-w-3xl">
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="relative overflow-hidden rounded-3xl p-8 text-white">
        <div className="bg-gradient-accent absolute inset-0" />
        <div className="relative flex items-end justify-between gap-6">
          <div>
            <div className="text-sm font-semibold uppercase tracking-wider text-white/75">{config ? MODE_INFO[config.mode].title : ''} · итоги</div>
            <div className="mt-1 text-3xl font-black">{grade}</div>
            <div className="mt-2 text-white/85">
              Угадано {correct} из {done.length} {plural(done.length, 'песни', 'песен', 'песен')} · точность {accuracy}% · лучшая серия {bestStreak}
            </div>
          </div>
          {config?.mode !== 'practice' && (
            <div className="text-right">
              <div className="text-xs font-semibold uppercase tracking-wider text-white/75">Очки</div>
              <div className="text-5xl font-black tabular-nums">{formatNumber(score)}</div>
            </div>
          )}
        </div>
      </motion.div>

      <div className="mt-6 grid gap-6 md:grid-cols-[240px_1fr]">
        <Card className="p-5">
          <div className="mb-4 text-sm font-semibold">С какой попытки</div>
          <div className="space-y-2.5">
            {[...hist, lost].map((n, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="w-12 shrink-0 text-muted">{i < 3 ? formatSeconds(stages[i]) : 'мимо'}</span>
                <div className="h-6 flex-1 overflow-hidden rounded-md bg-fg/5">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(n / max) * 100}%` }}
                    transition={{ delay: 0.1 * i, duration: 0.5 }}
                    className={cx('h-full rounded-md', i < 3 ? 'bg-gradient-accent' : 'bg-bad/50')}
                  />
                </div>
                <span className="w-5 text-right font-semibold tabular-nums">{n}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="max-h-[360px] overflow-y-auto p-2">
          {done.length === 0 && <div className="p-4 text-sm text-muted">Ни одного раунда не сыграно.</div>}
          {done.map((r, i) => (
            <div key={i} className="flex items-center gap-3 rounded-xl p-2.5">
              <Cover song={r.song} url={r.coverUrl} className="h-11 w-11 rounded-lg" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{r.song.title}</div>
                <div className="truncate text-sm text-muted">{r.song.artist}</div>
              </div>
              {r.status === 'won' ? (
                <span className="rounded-full bg-good/15 px-2.5 py-1 text-xs font-semibold text-good">{formatSeconds(stages[r.stage])}</span>
              ) : (
                <span className="rounded-full bg-bad/10 px-2.5 py-1 text-xs font-semibold text-bad">мимо</span>
              )}
              {config?.mode !== 'practice' && <span className="w-14 text-right text-sm font-semibold tabular-nums">+{r.points}</span>}
            </div>
          ))}
        </Card>
      </div>

      <div className="mt-6 flex justify-center gap-3">
        {config?.mode !== 'daily' && (
          <Button variant="primary" size="lg" onClick={again}>
            <RotateCcw size={18} /> Ещё раз
          </Button>
        )}
        <Button size="lg" onClick={quit}>
          <Home size={18} /> В меню
        </Button>
      </div>
    </div>
  )
}
