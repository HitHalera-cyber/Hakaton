import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowRight,
  Check,
  Copy,
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
  Timer,
  Users,
  X
} from 'lucide-react'
import { useCallback, useEffect, useRef } from 'react'
import { ChoiceGrid } from '@/components/ChoiceGrid'
import { Cover } from '@/components/Cover'
import { PartyBar } from '@/components/PartyBar'
import { SearchBox, type SearchBoxHandle } from '@/components/SearchBox'
import { StageTimeline } from '@/components/StageTimeline'
import { Button, Card, cx, Kbd } from '@/components/ui'
import { Visualizer } from '@/components/Visualizer'
import { YearPicker } from '@/components/YearPicker'
import { usePlayback } from '@/hooks/usePlayback'
import { api } from '@/lib/api'
import { audio, EFFECTS } from '@/lib/audio'
import { formatNumber, formatSeconds, plural } from '@/lib/format'
import { answerKind, BLITZ_SECONDS, BOT_LEVELS, hintsFor, MAX_HINTS, MODE_INFO, streakMultiplier, SURVIVAL_LIVES, YEAR_WIN_DISTANCE, type BotLevel, type Round } from '@/lib/game'
import { shareText } from '@/lib/progress'
import { stagesOf, useGame } from '@/store/game'
import { replay } from '@/store/launch'
import { useArtistIndex, useLibrary } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useUi } from '@/store/ui'

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
  return config ? stagesOf(config) : [1, 3, 5]
}

function BlitzClock() {
  const left = useGame((s) => s.blitzLeft)
  const sec = Math.ceil(left / 1000)
  const frac = left / (BLITZ_SECONDS * 1000)
  return (
    <div className="mb-5">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="flex items-center gap-1.5 font-semibold">
          <Timer size={16} className={cx(sec <= 10 ? 'text-bad' : 'text-accent')} /> Блиц
        </span>
        <motion.span key={sec} initial={{ scale: 1.2 }} animate={{ scale: 1 }} className={cx('text-lg font-black tabular-nums', sec <= 10 && 'text-bad')}>
          {Math.floor(sec / 60)}:{String(sec % 60).padStart(2, '0')}
        </motion.span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-fg/10">
        <div
          className={cx('h-full rounded-full transition-[width] duration-200 ease-linear', sec <= 10 ? 'bg-bad' : 'bg-gradient-accent')}
          style={{ width: `${frac * 100}%` }}
        />
      </div>
    </div>
  )
}

function Header() {
  const { config, rounds, score, streak, lives, finish, botScore } = useGame()
  const profile = useSettings((s) => s.profileEmoji)
  if (!config) return null
  const effect = config.effect && config.effect !== 'none' ? EFFECTS[config.effect] : null
  const roundNo = rounds.length || 1
  const endless = config.mode === 'survival' || config.mode === 'practice' || !Number.isFinite(config.rounds)
  const scored = config.mode !== 'practice' && config.mode !== 'party'
  return (
    <div className="mb-6 flex items-center gap-4">
      <div className="min-w-0">
        <div className="truncate text-xs font-semibold uppercase tracking-wider text-muted">
          {config.source ? `${config.source.icon ?? ''} ${config.source.label} · ` : ''}
          {MODE_INFO[config.mode].title}
        </div>
        <div className="text-xl font-bold">{endless ? `Песня ${roundNo}` : `Раунд ${roundNo} из ${config.rounds}`}</div>
      </div>
      {effect && (
        <span className="rounded-full bg-accent/12 px-3 py-1 text-xs font-semibold text-accent" title={`${effect.hint}. Очки ×${effect.bonus}`}>
          {effect.emoji} {effect.label} · ×{effect.bonus}
        </span>
      )}
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
          {streak >= 2 && scored && (
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
        {config.mode === 'duel' && (
          <div className="glass rounded-xl px-4 py-1.5 text-right" title={`Бот «${BOT_LEVELS[config.bot ?? 'mid'].label}»`}>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">{BOT_LEVELS[config.bot ?? 'mid'].emoji} Бот</div>
            <motion.div key={botScore} initial={{ scale: 1.25 }} animate={{ scale: 1 }} className="text-lg font-bold tabular-nums">
              {formatNumber(botScore)}
            </motion.div>
          </div>
        )}
        {scored && (
          <div className="glass rounded-xl px-4 py-1.5 text-right">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">{config.mode === 'duel' ? `${profile} Вы` : 'Очки'}</div>
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
  const { phase, rounds, config, buzzed, lockedOut, partyScores, playStage, playReveal, guess, guessYear, guessArtist, tickBlitz, buzz, skip, hint, next } =
    useGame()
  const artists = useArtistIndex()
  const visualizer = useSettings((s) => s.visualizer)
  const stages = useStages()
  const playback = usePlayback()
  const searchRef = useRef<SearchBoxHandle>(null)
  const round: Round | undefined = rounds[rounds.length - 1]
  const playing = phase === 'playing'
  const reveal = phase === 'reveal'
  const kind = config ? answerKind(config.mode) : 'search'
  const party = config?.mode === 'party'
  const players = config?.players ?? []

  useEffect(() => {
    if (playing && (kind === 'search' || kind === 'artist') && (!party || buzzed !== null)) searchRef.current?.focus()
  }, [playing, round?.song.id, kind, party, buzzed])

  // Blitz clock: runs only while a clip is being guessed.
  useEffect(() => {
    if (config?.mode !== 'blitz' || !playing) return
    let last = performance.now()
    const id = setInterval(() => {
      const now = performance.now()
      tickBlitz(now - last)
      last = now
    }, 100)
    return () => clearInterval(id)
  }, [config?.mode, playing, tickBlitz])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inInput = e.target instanceof HTMLInputElement
      const typing = inInput && (e.target as HTMLInputElement).value !== ''
      if (reveal && e.key === 'Enter') {
        e.preventDefault()
        void next()
      } else if (reveal && e.code === 'Space') {
        e.preventDefault()
        if (audio.state().playing) audio.stop()
        else playReveal()
      } else if (playing && party && buzzed === null && /^[1-4]$/.test(e.key)) {
        e.preventDefault()
        buzz(Number(e.key) - 1)
      } else if (playing && e.code === 'Space' && !typing && !(inInput && (e.target as HTMLInputElement).type === 'range')) {
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
  }, [playing, reveal, party, buzzed, next, playReveal, playStage, skip, hint, buzz])

  const pickChoice = useCallback((song: Parameters<typeof guess>[0]) => guess(song), [guess])

  return (
    <div className="mx-auto max-w-3xl">
      <Header />
      {config?.mode === 'blitz' && <BlitzClock />}
      {party && (
        <div className="mb-5">
          <PartyBar players={players} scores={partyScores} buzzed={buzzed} lockedOut={lockedOut} onBuzz={buzz} live={playing} />
        </div>
      )}
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
                {!reveal && <StageTimeline stages={stages} stage={round.stage} elapsed={playback.elapsed} playing={playback.playing} />}
                {reveal && (
                  <div className="text-sm text-muted">{playback.playing ? 'Звучит превью песни…' : 'Нажмите ▶, чтобы послушать ещё раз'}</div>
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
                {!party && (
                  <Button variant="ghost" onClick={hint} disabled={round.hints >= MAX_HINTS}>
                    <Lightbulb size={16} /> Подсказка ({MAX_HINTS - round.hints})
                  </Button>
                )}
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
                {kind === 'choice' && round.options && (
                  <ChoiceGrid options={round.options} wrongIds={round.guesses.map((g) => g.songId)} onPick={pickChoice} />
                )}
                {kind === 'year' && <YearPicker key={round.song.id} onSubmit={guessYear} />}
                {kind === 'artist' && (
                  <SearchBox
                    ref={searchRef}
                    index={artists.index}
                    onPick={(a) => guessArtist(a.title)}
                    excludeIds={round.guesses.map((g) => g.songId)}
                    describe={(a) => {
                      const n = artists.counts.get(a.title) ?? 0
                      return `${n} ${plural(n, 'песня', 'песни', 'песен')} в базе`
                    }}
                    placeholder="Кто поёт? Начните вводить имя исполнителя или группы…"
                  />
                )}
                {kind === 'search' && (
                  <>
                    {party && buzzed === null ? (
                      <div className="glass flex h-14 items-center justify-center gap-2 rounded-2xl text-sm text-muted">
                        <Users size={16} /> Кто узнал — жмите свою клавишу <Kbd>1</Kbd>–<Kbd>{players.length}</Kbd> или карточку игрока
                      </div>
                    ) : (
                      <SearchBox
                        ref={searchRef}
                        onPick={guess}
                        excludeIds={round.guesses.map((g) => g.songId)}
                        placeholder={
                          party && buzzed !== null
                            ? `${players[buzzed]?.name}, что это за песня?`
                            : 'Что это за песня? Начните вводить название или исполнителя…'
                        }
                      />
                    )}
                  </>
                )}
                {config?.mode === 'duel' && round.botStage != null && round.stage > round.botStage && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-2 rounded-2xl bg-warn/15 px-4 py-2.5 text-sm font-semibold text-warn"
                  >
                    {BOT_LEVELS[config.bot ?? 'mid'].emoji} Бот уже узнал эту песню за {formatSeconds(stages[round.botStage])} — догоняйте!
                  </motion.div>
                )}
                <HintsAndGuesses round={round} kind={kind} players={players} />
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
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - progress)} />
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

function HintsAndGuesses({ round, kind, players }: { round: Round; kind: ReturnType<typeof answerKind>; players: { name: string; color: string }[] }) {
  const hints = hintsFor(round.song, kind).slice(0, round.hints)
  const guesses = kind === 'choice' ? round.guesses.filter((g) => g.skipped) : round.guesses
  if (!hints.length && !guesses.length) {
    return (
      <p className="px-1 text-sm text-muted">
        {kind === 'year'
          ? 'Назовите год выхода песни: точный ответ — полные очки, ошибка в 1–2 года тоже засчитывается.'
          : 'Неверный ответ открывает отрывок подлиннее, но приносит меньше очков.'}
      </p>
    )
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
        {guesses.map((g, i) => (
          <motion.div
            key={`${g.songId}-${i}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-sm"
          >
            {g.skipped ? <SkipForward size={16} className="text-muted" /> : <X size={16} className="text-bad" />}
            {g.player !== undefined && players[g.player] && (
              <span className="rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ background: players[g.player].color }}>
                {players[g.player].name}
              </span>
            )}
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

function FavoriteButton({ songId }: { songId: string }) {
  const fav = useLibrary((s) => s.favorites.includes(songId))
  const toggle = useLibrary((s) => s.toggleFavorite)
  return (
    <motion.button
      whileTap={{ scale: 0.85 }}
      onClick={() => toggle(songId)}
      className={cx(
        'flex h-10 w-10 items-center justify-center rounded-full transition cursor-pointer',
        fav ? 'bg-bad/15 text-bad' : 'bg-fg/5 text-muted hover:text-bad'
      )}
      title={fav ? 'Убрать из избранного' : 'В избранное'}
      aria-pressed={fav}
    >
      <Heart size={18} fill={fav ? 'currentColor' : 'none'} />
    </motion.button>
  )
}

function RevealBanner({ round, stages }: { round: Round; stages: number[] }) {
  const { config } = useGame()
  const won = round.status === 'won'
  const players = config?.players ?? []
  if (config && answerKind(config.mode) === 'year' && round.yearGuess !== undefined) {
    const d = Math.abs(round.yearGuess - round.song.year)
    return (
      <span className="flex items-center gap-2">
        {d === 0 ? '🎯 Точно в год!' : won ? `Почти! Ошибка ${d} ${plural(d, 'год', 'года', 'лет')}` : `Мимо на ${d} ${plural(d, 'год', 'года', 'лет')}`}
        <span className="font-normal opacity-80">· ваш ответ {round.yearGuess}, верно {round.song.year}</span>
        {round.points > 0 && <span className="ml-auto text-base">+{formatNumber(round.points)}</span>}
      </span>
    )
  }
  if (won) {
    const winner = round.winner !== undefined ? players[round.winner] : undefined
    return (
      <span className="flex items-center gap-2">
        <Check size={16} /> {winner ? `${winner.name} угадывает` : 'Угадано'} за {formatSeconds(stages[round.stage])}
        {round.points > 0 && <span className="ml-auto text-base">+{formatNumber(round.points)}</span>}
        {winner && <span className="ml-auto text-base">+{formatNumber(useGame.getState().lastPoints)}</span>}
      </span>
    )
  }
  return (
    <span className="flex items-center gap-2">
      <X size={16} /> Не угадано — это была…
      {config?.mode === 'survival' && <span className="ml-auto">−1 жизнь</span>}
    </span>
  )
}

function RevealCard({ round, stages }: { round: Round; stages: number[] }) {
  const { next, config, lives } = useGame()
  const won = round.status === 'won'
  const lastRound = config && (config.mode === 'survival' ? lives <= 0 : useGame.getState().rounds.length >= config.rounds)
  const yearMode = config && answerKind(config.mode) === 'year'
  const good = yearMode ? round.yearGuess !== undefined && Math.abs(round.yearGuess - round.song.year) <= YEAR_WIN_DISTANCE : won
  return (
    <Card className="mt-5 overflow-hidden">
      <div className={cx('px-6 py-3 text-sm font-semibold', good ? 'bg-good/15 text-good' : 'bg-bad/10 text-bad')}>
        <RevealBanner round={round} stages={stages} />
      </div>
      {config?.mode === 'duel' && round.botStage !== undefined && <DuelLine round={round} stages={stages} />}
      <div className="flex items-center gap-6 p-6">
        <motion.div initial={{ rotate: -8, scale: 0.8 }} animate={{ rotate: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 200 }}>
          <Cover song={round.song} url={round.coverUrl} className="h-36 w-36 rounded-2xl shadow-2xl" />
        </motion.div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="text-2xl font-bold leading-tight">{round.song.title}</div>
              <div className="mt-1 text-lg text-muted">{round.song.artist}</div>
            </div>
            <FavoriteButton songId={round.song.id} />
          </div>
          <div className="mt-2 text-sm text-muted">{[round.song.year > 0 && round.song.year, round.album].filter(Boolean).join(' · ')}</div>
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

/** Duel: who was faster in this round. */
function DuelLine({ round, stages }: { round: Round; stages: number[] }) {
  const bot = useGame((s) => BOT_LEVELS[s.config?.bot ?? 'mid'])
  const me = round.status === 'won' ? round.stage : null
  const b = round.botStage ?? null
  const verdict =
    me === null && b === null
      ? 'Никто не узнал'
      : b === null || (me !== null && me < b)
        ? 'Раунд ваш!'
        : me === null || b < me
          ? 'Раунд за ботом'
          : 'Ничья в раунде'
  return (
    <div className="flex items-center gap-3 border-b border-line px-6 py-2.5 text-sm">
      <span className="text-lg">{bot.emoji}</span>
      <span className="text-muted">{b === null ? 'Бот не узнал песню' : `Бот узнал за ${formatSeconds(stages[b])}`}</span>
      <span className="ml-auto font-semibold">{verdict}</span>
    </div>
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
  const { error, config, quit } = useGame()
  return (
    <div className="mx-auto mt-16 max-w-lg text-center">
      <div className="mb-4 text-5xl">🎧</div>
      <h2 className="text-xl font-bold">Не получилось начать игру</h2>
      <p className="mt-2 text-muted">{error}</p>
      <div className="mt-6 flex justify-center gap-3">
        {config && (
          <Button variant="primary" onClick={replay}>
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

function PartyPodium() {
  const { config, partyScores } = useGame()
  const players = (config?.players ?? []).map((p, i) => ({ ...p, score: partyScores[i] ?? 0 })).sort((a, b) => b.score - a.score)
  const medals = ['🥇', '🥈', '🥉', '4']
  return (
    <div className="mt-6 grid gap-3" style={{ gridTemplateColumns: `repeat(${players.length}, minmax(0, 1fr))` }}>
      {players.map((p, i) => (
        <motion.div
          key={p.name + i}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 * i }}
          className="glass rounded-2xl p-4 text-center"
          style={i === 0 ? { borderColor: p.color, boxShadow: `0 10px 40px -15px ${p.color}` } : undefined}
        >
          <div className="text-3xl">{medals[i]}</div>
          <div className="mt-1 flex items-center justify-center gap-2 font-semibold">
            <span className="h-3 w-3 rounded-full" style={{ background: p.color }} />
            {p.name}
          </div>
          <div className="mt-1 text-2xl font-black tabular-nums">{formatNumber(p.score)}</div>
        </motion.div>
      ))}
    </div>
  )
}

function DuelScore({ you, bot, level }: { you: number; bot: number; level: BotLevel }) {
  const emoji = useSettings((s) => s.profileEmoji)
  const name = useSettings((s) => s.profileName) || 'Вы'
  const total = Math.max(1, you + bot)
  return (
    <Card className="mt-6 p-5">
      <div className="mb-3 flex items-center justify-between text-lg font-bold">
        <span>
          {emoji} {name} <span className="tabular-nums">{formatNumber(you)}</span>
        </span>
        <span>
          <span className="tabular-nums">{formatNumber(bot)}</span> {BOT_LEVELS[level].label} {BOT_LEVELS[level].emoji}
        </span>
      </div>
      <div className="flex h-3 overflow-hidden rounded-full bg-fg/10">
        <motion.div className="bg-gradient-accent h-full" initial={{ width: '50%' }} animate={{ width: `${(you / total) * 100}%` }} transition={{ duration: 0.8 }} />
        <div className="h-full flex-1 bg-warn/60" />
      </div>
    </Card>
  )
}

function Results() {
  const { rounds, score, bestStreak, config, quit, partyScores, botScore } = useGame()
  const duel = config?.mode === 'duel'
  const toast = useUi((u) => u.toast)
  const done = rounds.filter((r) => r.status !== 'playing')
  const correct = done.filter((r) => r.status === 'won').length
  const accuracy = done.length ? Math.round((correct / done.length) * 100) : 0
  const stages = useStages()
  const kind = config ? answerKind(config.mode) : 'search'
  const party = config?.mode === 'party'
  const hist = [0, 1, 2].map((stage) => done.filter((r) => r.status === 'won' && r.stage === stage).length)
  const lost = done.length - correct
  const max = Math.max(1, ...hist, lost)
  const top = Math.max(0, ...partyScores)
  const leaders = partyScores.filter((p) => p === top).length
  const winner = party && config?.players && top > 0 && leaders === 1 ? config.players[partyScores.indexOf(top)] : undefined
  const grade = duel
    ? score > botScore
      ? 'Победа над ботом! 🏆'
      : score < botScore
        ? 'Бот оказался быстрее 🤖'
        : 'Ничья! 🤝'
    : winner
    ? `Победа: ${winner.name}! 🏆`
    : party
      ? 'Ничья! 🤝'
      : accuracy >= 90
      ? 'Легенда! 🎸'
      : accuracy >= 70
        ? 'Меломан 🎧'
        : accuracy >= 40
          ? 'Неплохо 🎶'
          : 'Есть куда расти 🎵'

  const share = async () => {
    if (!config) return
    try {
      await navigator.clipboard.writeText(shareText(config, rounds, score))
      toast({ title: 'Результат скопирован', body: 'Вставьте его в чат друзьям', icon: '📋' })
    } catch {
      toast({ title: 'Не удалось скопировать', tone: 'error', icon: '⚠️' })
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="relative overflow-hidden rounded-3xl p-8 text-white">
        <div className="bg-gradient-accent absolute inset-0" />
        <div className="relative flex items-end justify-between gap-6">
          <div>
            <div className="text-sm font-semibold uppercase tracking-wider text-white/75">
              {config?.source ? `${config.source.label} · ` : ''}
              {config ? MODE_INFO[config.mode].title : ''} · итоги
            </div>
            <div className="mt-1 text-3xl font-black">{grade}</div>
            <div className="mt-2 text-white/85">
              Угадано {correct} из {done.length} {plural(done.length, 'песни', 'песен', 'песен')} · точность {accuracy}%{!party && ` · лучшая серия ${bestStreak}`}
            </div>
          </div>
          {config?.mode !== 'practice' && !party && (
            <div className="text-right">
              <div className="text-xs font-semibold uppercase tracking-wider text-white/75">Очки</div>
              <div className="text-5xl font-black tabular-nums">{formatNumber(score)}</div>
            </div>
          )}
        </div>
      </motion.div>

      {party && <PartyPodium />}
      {duel && config && <DuelScore you={score} bot={botScore} level={config.bot ?? 'mid'} />}

      <div className="mt-6 grid gap-6 md:grid-cols-[240px_1fr]">
        <Card className="p-5">
          <div className="mb-4 text-sm font-semibold">{kind === 'year' ? 'Точность по годам' : 'С какой попытки'}</div>
          {kind === 'year' ? (
            <YearSummary rounds={done} />
          ) : (
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
          )}
        </Card>
        <Card className="max-h-[360px] overflow-y-auto p-2">
          {done.length === 0 && <div className="p-4 text-sm text-muted">Ни одного раунда не сыграно.</div>}
          {done.map((r, i) => (
            <div key={i} className="flex items-center gap-3 rounded-xl p-2.5">
              <Cover song={r.song} url={r.coverUrl} className="h-11 w-11 rounded-lg" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{r.song.title}</div>
                <div className="truncate text-sm text-muted">
                  {r.song.artist}
                  {kind === 'year' && ` · ${r.song.year}`}
                </div>
              </div>
              {kind === 'year' ? (
                <span className={cx('rounded-full px-2.5 py-1 text-xs font-semibold', r.status === 'won' ? 'bg-good/15 text-good' : 'bg-bad/10 text-bad')}>
                  {r.yearGuess ?? '—'}
                </span>
              ) : r.status === 'won' ? (
                <span
                  className="rounded-full bg-good/15 px-2.5 py-1 text-xs font-semibold text-good"
                  style={party && r.winner !== undefined && config?.players ? { background: config.players[r.winner].color, color: 'white' } : undefined}
                >
                  {party && r.winner !== undefined && config?.players ? config.players[r.winner].name : formatSeconds(stages[r.stage])}
                </span>
              ) : (
                <span className="rounded-full bg-bad/10 px-2.5 py-1 text-xs font-semibold text-bad">мимо</span>
              )}
              {config?.mode !== 'practice' && !party && <span className="w-14 text-right text-sm font-semibold tabular-nums">+{r.points}</span>}
              <FavoriteButton songId={r.song.id} />
            </div>
          ))}
        </Card>
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {config?.mode !== 'daily' && (
          <Button variant="primary" size="lg" onClick={replay}>
            <RotateCcw size={18} /> Ещё раз
          </Button>
        )}
        <Button size="lg" onClick={() => void share()} disabled={!done.length}>
          <Copy size={18} /> Поделиться
        </Button>
        <Button size="lg" onClick={quit}>
          <Home size={18} /> В меню
        </Button>
      </div>
    </div>
  )
}

function YearSummary({ rounds }: { rounds: Round[] }) {
  const diffs = rounds.map((r) => (r.yearGuess === undefined ? null : Math.abs(r.yearGuess - r.song.year))).filter((d): d is number => d !== null)
  const exact = diffs.filter((d) => d === 0).length
  const avg = diffs.length ? diffs.reduce((a, b) => a + b, 0) / diffs.length : 0
  return (
    <div className="space-y-3 text-sm">
      <div className="flex justify-between">
        <span className="text-muted">Точно в год</span>
        <span className="font-semibold tabular-nums">{exact}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-muted">В пределах 2 лет</span>
        <span className="font-semibold tabular-nums">{diffs.filter((d) => d <= YEAR_WIN_DISTANCE).length}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-muted">Средняя ошибка</span>
        <span className="font-semibold tabular-nums">
          {avg.toFixed(1).replace('.', ',')} {plural(Math.round(avg), 'год', 'года', 'лет')}
        </span>
      </div>
    </div>
  )
}
