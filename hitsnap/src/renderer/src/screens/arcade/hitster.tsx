import { AnimatePresence, motion } from 'framer-motion'
import { Heart, Music2, Play, Pause, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { cx } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { plural } from '@/lib/format'
import { fitsSlot } from '@/lib/arcade'
import { cue, finish, GameOver, usePool } from './kit'

// «Музыкальная лента» — like the Hitster card game: a song plays with its
// name hidden, and the player slots it into their own timeline by year.
// A wrong slot costs a life; ten cards on the timeline wins.

const GOAL = 10
const LIVES = 3

interface Placed {
  slot: number
  ok: boolean
}


export function HitsterGame() {
  const pool = usePool()
  const preview = usePreview()
  const draw = useCallback((used: Song[]) => {
    for (let i = 0; i < 40; i++) {
      const s = pool[Math.floor(Math.random() * pool.length)]
      if (!used.some((u) => u.id === s.id)) return s
    }
    return pool[0]
  }, [pool])

  const [cards, setCards] = useState<Song[]>(() => [draw([])])
  const [current, setCurrent] = useState<Song>(() => draw(cards))
  const [lives, setLives] = useState(LIVES)
  const [placed, setPlaced] = useState<Placed | null>(null)
  const [over, setOver] = useState<'win' | 'lose' | null>(null)

  // Every new mystery card starts playing by itself.
  useEffect(() => {
    if (!over) void preview.play(current, { quiet: true })
  }, [current.id])

  const years = cards.map((c) => c.year)
  const place = (slot: number) => {
    if (placed || over) return
    preview.stop()
    const ok = fitsSlot(years, slot, current.year)
    setPlaced({ slot, ok })
    cue(ok ? 'correct' : 'wrong')
    const nextCards = ok ? [...cards.slice(0, slot), current, ...cards.slice(slot)] : cards
    const nextLives = ok ? lives : lives - 1
    setTimeout(() => {
      setCards(nextCards)
      setLives(nextLives)
      setPlaced(null)
      const score = nextCards.length - 1
      if (nextCards.length >= GOAL) {
        setOver('win')
        finish('hitster', score, score * 60 + 200, true)
      } else if (nextLives <= 0) {
        setOver('lose')
        finish('hitster', score, score * 60, false)
      } else setCurrent(draw([...nextCards, current]))
    }, ok ? 1100 : 2000)
  }

  const again = () => {
    const first = draw([])
    setCards([first])
    setCurrent(draw([first]))
    setLives(LIVES)
    setPlaced(null)
    setOver(null)
  }

  const playing = preview.current === current.id
  const slotLabel = (i: number) =>
    i === 0 ? `раньше ${years[0]}` : i === years.length ? `позже ${years[years.length - 1]}` : `${years[i - 1]} – ${years[i]}`

  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <div className="text-lg font-semibold">Куда на ленте эта песня?</div>
        <div className="ml-auto flex gap-1" title="Жизни">
          {Array.from({ length: LIVES }, (_, i) => (
            <Heart key={i} size={20} className={cx('text-bad transition', i >= lives && 'opacity-20')} fill="currentColor" />
          ))}
        </div>
        <div className="rounded-full bg-accent/15 px-3 py-1 text-sm font-bold text-accent">
          {cards.length} / {GOAL}
        </div>
      </div>

      {!over && (
        <motion.div key={current.id} initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-5 flex items-center gap-5 rounded-3xl border border-accent/40 bg-accent/8 p-5">
          <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-2xl">
            {placed ? (
              <Cover song={current} className="h-24 w-24" />
            ) : (
              <div className="bg-gradient-accent flex h-24 w-24 items-center justify-center text-5xl font-black text-white">?</div>
            )}
          </div>
          <div className="min-w-0 flex-1">
            {placed ? (
              <>
                <div className="truncate text-xl font-bold">{current.title}</div>
                <div className="truncate text-muted">{current.artist}</div>
                <div className={cx('mt-1 text-2xl font-black tabular-nums', placed.ok ? 'text-good' : 'text-bad')}>
                  {current.year} {placed.ok ? '✓' : '✗'}
                </div>
              </>
            ) : (
              <>
                <div className="text-xl font-bold">Загадочная песня</div>
                <div className="text-sm text-muted">Послушайте и выберите место на ленте между песнями по году выхода.</div>
              </>
            )}
          </div>
          {!placed && (
            <button
              onClick={() => void preview.toggle(current)}
              className="bg-gradient-accent flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white shadow-lg shadow-accent/30 transition hover:scale-105 cursor-pointer"
              aria-label={playing ? 'Пауза' : 'Слушать'}
            >
              {preview.loading === current.id ? <Loader2 size={22} className="animate-spin" /> : playing ? <Pause size={22} fill="currentColor" /> : <Play size={22} fill="currentColor" className="ml-1" />}
            </button>
          )}
        </motion.div>
      )}

      <div className="space-y-1.5">
        {cards.map((card, i) => (
          <div key={card.id}>
            <Slot label={slotLabel(i)} onClick={() => place(i)} hidden={!!over} state={placed?.slot === i ? (placed.ok ? 'good' : 'bad') : null} />
            <motion.div layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-3">
              <span className="text-gradient w-16 text-center text-xl font-black tabular-nums">{card.year}</span>
              <Cover song={card} className="h-11 w-11 rounded-xl" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{card.title}</div>
                <div className="truncate text-sm text-muted">{card.artist}</div>
              </div>
              <Music2 size={16} className="text-muted" />
            </motion.div>
          </div>
        ))}
        <Slot label={slotLabel(cards.length)} onClick={() => place(cards.length)} hidden={!!over} state={placed?.slot === cards.length ? (placed.ok ? 'good' : 'bad') : null} />
      </div>

      {over && (
        <GameOver
          title={over === 'win' ? 'Лента собрана! 🎉' : `Лента из ${cards.length} ${plural(cards.length, 'песни', 'песен', 'песен')}`}
          detail={over === 'win' ? `Все ${GOAL} песен на своих местах.` : 'Жизни кончились. Попробуйте собрать ленту из десяти песен.'}
          onAgain={again}
        />
      )}
    </>
  )
}

function Slot({ label, onClick, hidden, state }: { label: string; onClick: () => void; hidden: boolean; state: 'good' | 'bad' | null }) {
  return (
    <AnimatePresence initial={false}>
      {!hidden && (
        <motion.button
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          onClick={onClick}
          className={cx(
            'mb-1.5 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed py-2 text-sm font-semibold transition cursor-pointer',
            state === 'good' ? 'border-good bg-good/15 text-good' : state === 'bad' ? 'border-bad bg-bad/10 text-bad' : 'border-accent/30 text-accent/80 hover:border-accent hover:bg-accent/10'
          )}
        >
          ＋ Сюда · {label}
        </motion.button>
      )}
    </AnimatePresence>
  )
}
