import { AnimatePresence, motion } from 'framer-motion'
import { Check, Eye, EyeOff, Heart, Loader2, Pause, Play, Radio, SkipForward, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { Genre, Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { Visualizer } from '@/components/Visualizer'
import { Button, Card, Chip, cx } from '@/components/ui'
import { usePlayback } from '@/hooks/usePlayback'
import { api } from '@/lib/api'
import { audio } from '@/lib/audio'
import { decadeOf, GENRE_LABELS, GENRE_STYLE } from '@/lib/game'
import { shuffle } from '@/lib/random'
import { useAllSongs, useLibrary } from '@/store/library'
import { useUi } from '@/store/ui'

// «Радио»: previews play one after another with the answer hidden — guess
// out loud, then see if you were right. Relaxed, no points, no clock.

type Station = { kind: 'all' } | { kind: 'fav' } | { kind: 'genre'; genre: Genre } | { kind: 'decade'; decade: number }

const DECADES = [1970, 1980, 1990, 2000, 2010, 2020]
/** Seconds of listening before the answer shows by itself. */
const AUTO_REVEAL = 12
const MAX_FAILURES = 6

interface Track {
  song: Song
  buffer: AudioBuffer
  coverUrl?: string
}

async function loadTrack(song: Song): Promise<Track | null> {
  try {
    const t = await api.resolveTrack(song)
    if (!t) return null
    return { song, buffer: await audio.decode(t.audio), coverUrl: t.coverUrl }
  } catch {
    return null
  }
}

const sameStation = (a: Station, b: Station): boolean => JSON.stringify(a) === JSON.stringify(b)

export function RadioScreen() {
  const songs = useAllSongs()
  const favorites = useLibrary((s) => s.favorites)
  const toggleFavorite = useLibrary((s) => s.toggleFavorite)
  const [station, setStation] = useState<Station>({ kind: 'all' })
  const [track, setTrack] = useState<Track | null>(null)
  const [loading, setLoading] = useState(false)
  const [paused, setPaused] = useState(false)
  const [hide, setHide] = useState(true)
  const [revealed, setRevealed] = useState(false)
  const [tally, setTally] = useState({ knew: 0, total: 0 })
  const [answered, setAnswered] = useState<boolean | null>(null)
  const playback = usePlayback()
  const queue = useRef<Song[]>([])
  const session = useRef(0)
  const next = useRef<Promise<Track | null> | null>(null)
  const pausedAt = useRef(0)
  /** Where in the preview playback (re)started — after a pause it resumes mid-song. */
  const base = useRef(0)
  const pos = paused ? pausedAt.current : base.current + playback.elapsed

  const pool = useMemo(() => {
    const fav = new Set(favorites)
    return songs.filter((s) => {
      if (station.kind === 'fav') return fav.has(s.id)
      if (s.tier > 2 && station.kind === 'all') return false
      if (station.kind === 'genre') return s.genre === station.genre
      if (station.kind === 'decade') return s.year > 0 && decadeOf(s.year) === station.decade
      return true
    })
  }, [songs, favorites, station])

  const take = (): Song | undefined => {
    if (!queue.current.length) queue.current = shuffle(pool)
    return queue.current.shift()
  }

  const play = async () => {
    const id = ++session.current
    audio.stop()
    setLoading(true)
    setRevealed(false)
    setAnswered(null)
    setPaused(false)
    for (let failures = 0; failures < MAX_FAILURES; ) {
      const pending = next.current
      next.current = null
      const t = pending ? await pending : await (async () => {
        const s = take()
        return s ? loadTrack(s) : null
      })()
      if (id !== session.current) return
      if (!t) {
        failures++
        if (!pool.length) break
        continue
      }
      setTrack(t)
      setLoading(false)
      base.current = 0
      audio.play(t.buffer, 0)
      const upcoming = take()
      if (upcoming) next.current = loadTrack(upcoming)
      return
    }
    setLoading(false)
    setTrack(null)
    useUi.getState().toast({ title: 'Радио молчит', body: 'Не удалось загрузить песни — проверьте интернет или выберите другую станцию', tone: 'error', icon: '📻' })
  }

  // A new station starts from scratch.
  const tune = (s: Station) => {
    if (sameStation(s, station) && track) return
    queue.current = []
    next.current = null
    setStation(s)
  }
  const tuned = useRef(false)
  useEffect(() => {
    if (!tuned.current) return
    void play()
  }, [station])

  // Leaving the screen silences the radio.
  useEffect(
    () => () => {
      session.current++
      audio.stop()
    },
    []
  )

  // Show the answer after a while; move on when the preview ends.
  const live = !!track && !loading && !paused
  useEffect(() => {
    if (live && !revealed && pos >= AUTO_REVEAL) setRevealed(true)
  }, [live, revealed, pos])
  const wasPlaying = useRef(false)
  useEffect(() => {
    if (wasPlaying.current && !playback.playing && live) void play()
    wasPlaying.current = playback.playing
  }, [playback.playing])

  const start = () => {
    tuned.current = true
    void play()
  }
  const togglePause = () => {
    if (!track) return start()
    if (paused) {
      base.current = Math.min(pausedAt.current, track.buffer.duration - 0.5)
      audio.play(track.buffer, base.current)
      setPaused(false)
    } else {
      pausedAt.current = pos
      setPaused(true)
      audio.stop()
    }
  }
  const answer = (knew: boolean) => {
    setAnswered(knew)
    setRevealed(true)
    setTally((t) => ({ knew: t.knew + (knew ? 1 : 0), total: t.total + 1 }))
  }

  const showAnswer = !hide || revealed
  const fav = track ? favorites.includes(track.song.id) : false

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-black tracking-tight">
            <Radio size={28} className="text-accent" /> Радио
          </h1>
          <p className="mt-1 text-muted">Песни идут одна за другой, название скрыто. Угадывайте вслух — ответ откроется сам через {AUTO_REVEAL} секунд.</p>
        </div>
        {tally.total > 0 && (
          <div className="glass shrink-0 rounded-2xl px-4 py-2 text-right">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">Узнано</div>
            <div className="text-xl font-black tabular-nums">
              {tally.knew} из {tally.total}
            </div>
          </div>
        )}
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        <Chip active={station.kind === 'all'} onClick={() => tune({ kind: 'all' })}>
          🎶 Всё подряд
        </Chip>
        <Chip active={station.kind === 'fav'} onClick={() => tune({ kind: 'fav' })}>
          ❤️ Избранное
        </Chip>
        {DECADES.map((d) => (
          <Chip key={d} active={station.kind === 'decade' && station.decade === d} onClick={() => tune({ kind: 'decade', decade: d })}>
            {String(d).slice(2)}-е
          </Chip>
        ))}
        {(Object.keys(GENRE_LABELS) as Genre[]).map((g) => (
          <Chip key={g} active={station.kind === 'genre' && station.genre === g} onClick={() => tune({ kind: 'genre', genre: g })}>
            {GENRE_STYLE[g].emoji} {GENRE_LABELS[g]}
          </Chip>
        ))}
      </div>

      <Card className="relative overflow-hidden p-8">
        <div className="flex items-center gap-8">
          <div className="relative h-56 w-56 shrink-0">
            {track ? (
              <>
                <Cover song={track.song} url={track.coverUrl} className={cx('h-56 w-56 rounded-3xl shadow-2xl transition duration-700', !showAnswer && 'scale-95 blur-2xl')} />
                {!showAnswer && <div className="absolute inset-0 flex items-center justify-center text-7xl font-black text-white drop-shadow-lg">?</div>}
              </>
            ) : (
              <div className="bg-gradient-accent flex h-56 w-56 items-center justify-center rounded-3xl text-7xl shadow-2xl">📻</div>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <Visualizer className="mb-4 h-16 w-full" />
            <AnimatePresence mode="wait">
              <motion.div key={`${track?.song.id}-${showAnswer}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                {loading ? (
                  <div className="flex items-center gap-2 text-muted">
                    <Loader2 size={18} className="animate-spin" /> Ловим волну…
                  </div>
                ) : !track ? (
                  <div className="text-muted">Выберите станцию и нажмите ▶</div>
                ) : showAnswer ? (
                  <>
                    <div className="truncate text-3xl font-black leading-tight">{track.song.title}</div>
                    <div className="mt-1 truncate text-lg text-muted">
                      {track.song.artist}
                      {track.song.year > 0 && ` · ${track.song.year}`}
                    </div>
                    {answered !== null && (
                      <div className={cx('mt-2 text-sm font-semibold', answered ? 'text-good' : 'text-muted')}>{answered ? 'Вы узнали эту песню 👏' : 'Теперь будете знать'}</div>
                    )}
                  </>
                ) : (
                  <>
                    <div className="text-3xl font-black">Что это за песня?</div>
                    <div className="mt-1 text-muted">
                      {GENRE_LABELS[track.song.genre]} · ответ через {Math.max(0, Math.ceil(AUTO_REVEAL - pos))} с
                    </div>
                    <div className="mt-4 flex gap-2">
                      <Button variant="primary" onClick={() => answer(true)}>
                        <Check size={16} /> Узнал(а)!
                      </Button>
                      <Button onClick={() => answer(false)}>
                        <X size={16} /> Не знаю
                      </Button>
                    </div>
                  </>
                )}
              </motion.div>
            </AnimatePresence>
            <div className="mt-6 flex items-center gap-2">
              <button
                onClick={togglePause}
                className="bg-gradient-accent flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg shadow-accent/30 transition hover:scale-105 cursor-pointer"
                aria-label={track && !paused ? 'Пауза' : 'Играть'}
              >
                {track && !paused && !loading ? <Pause size={22} fill="currentColor" /> : <Play size={22} fill="currentColor" className="ml-1" />}
              </button>
              <Button variant="secondary" onClick={() => (tuned.current = true, void play())} disabled={loading}>
                <SkipForward size={16} /> Следующая
              </Button>
              {track && (
                <Button variant="ghost" onClick={() => toggleFavorite(track.song.id)} title="В избранное">
                  <Heart size={16} className={cx(fav && 'text-bad')} fill={fav ? 'currentColor' : 'none'} />
                </Button>
              )}
              <Button variant="ghost" className="ml-auto" onClick={() => setHide(!hide)} title={hide ? 'Показывать название сразу' : 'Скрывать название'}>
                {hide ? <EyeOff size={16} /> : <Eye size={16} />} {hide ? 'Ответ скрыт' : 'Ответ виден'}
              </Button>
            </div>
            {track && (
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-fg/10">
                <div className="bg-gradient-accent h-full" style={{ width: `${(pos / Math.max(1, track.buffer.duration)) * 100}%` }} />
              </div>
            )}
          </div>
        </div>
      </Card>
      <p className="mt-3 text-center text-xs text-muted">{pool.length} песен на станции</p>
    </div>
  )
}
