import { AnimatePresence, motion } from 'framer-motion'
import { Dices, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Genre } from '@shared/types'
import { audio, EFFECTS, type SoundEffect } from '@/lib/audio'
import { EMPTY_FILTERS, GENRE_LABELS, GENRE_STYLE, MODE_INFO, STATION_MODES, type GameMode } from '@/lib/game'
import { launch } from '@/store/launch'
import { useSettings } from '@/store/settings'
import { Modal } from './Modal'
import { Button } from './ui'

// «Рулетка»: three reels pick a mode, a genre and a sound effect at random.

const MODES = STATION_MODES.filter((m) => m !== 'practice')
const MODE_EMOJI: Partial<Record<GameMode, string>> = { classic: '🏆', survival: '❤️', blitz: '⏱️', duel: '🤖', quiz: '🧩', artist: '🎙️', year: '📅' }
const GENRES = Object.keys(GENRE_LABELS) as Genre[]
/** Effects are rarer than clean sound, so a spin is not always distorted. */
const EFFECT_REEL: SoundEffect[] = ['none', 'none', 'none', ...(Object.keys(EFFECTS) as SoundEffect[]).filter((e) => e !== 'none')]

const pick = <T,>(list: readonly T[]): T => list[Math.floor(Math.random() * list.length)]

interface Spin {
  mode: GameMode
  genre: Genre
  effect: SoundEffect
}

const random = (): Spin => ({ mode: pick(MODES), genre: pick(GENRES), effect: pick(EFFECT_REEL) })

function Reel({ label, value, sub, stopped }: { label: string; value: string; sub?: string; stopped: boolean }) {
  return (
    <div className="flex flex-col items-center">
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div
        className={`flex h-24 w-full flex-col items-center justify-center overflow-hidden rounded-2xl border px-2 text-center transition ${stopped ? 'border-accent bg-accent/10' : 'border-line bg-fg/5'}`}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.div
            key={value}
            initial={{ y: -30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 30, opacity: 0 }}
            transition={{ duration: stopped ? 0.3 : 0.07 }}
            className="text-sm font-bold leading-tight"
          >
            {sub && <div className="mb-1 text-2xl">{sub}</div>}
            {value}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

export function Roulette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [shown, setShown] = useState<Spin>(random)
  const [stopped, setStopped] = useState(3)
  const timers = useRef<number[]>([])

  const clear = () => {
    timers.current.forEach((t) => (clearTimeout(t), clearInterval(t)))
    timers.current = []
  }

  const roll = () => {
    clear()
    const final = random()
    let stop = 0
    let ticks = 0
    setStopped(0)
    // Spinning reels show random values; each one stops on the final value in turn.
    const ticker = window.setInterval(() => {
      const r = random()
      setShown({ mode: stop >= 1 ? final.mode : r.mode, genre: stop >= 2 ? final.genre : r.genre, effect: r.effect })
      if (ticks++ % 2 === 0 && useSettings.getState().sfx) audio.sfx('tick')
    }, 90)
    timers.current.push(ticker)
    ;[900, 1400, 1900].forEach((t, i) =>
      timers.current.push(
        window.setTimeout(() => {
          stop = i + 1
          setStopped(stop)
          if (stop === 3) {
            clearInterval(ticker)
            setShown(final)
            if (useSettings.getState().sfx) audio.sfx('correct')
          }
        }, t)
      )
    )
  }

  useEffect(() => {
    if (open) roll()
    return clear
  }, [open])

  const done = stopped >= 3
  const go = () => {
    const st = GENRE_STYLE[shown.genre]
    onClose()
    launch(shown.mode, {
      filters: { ...EMPTY_FILTERS, genres: [shown.genre], popularity: useSettings.getState().filters.popularity ?? 'all' },
      source: { label: `Рулетка · ${GENRE_LABELS[shown.genre]}`, icon: st.emoji },
      effect: shown.effect
    })
  }

  return (
    <Modal open={open} onClose={onClose} title="Рулетка">
      <p className="-mt-2 mb-4 text-sm text-muted">Случай выбирает режим, жанр и звуковой эффект. Рискнёте?</p>
      <div className="grid grid-cols-3 gap-2">
        <Reel label="Режим" value={MODE_INFO[shown.mode].title} sub={MODE_EMOJI[shown.mode]} stopped={stopped >= 1} />
        <Reel label="Жанр" value={GENRE_LABELS[shown.genre]} sub={GENRE_STYLE[shown.genre].emoji} stopped={stopped >= 2} />
        <Reel
          label="Эффект"
          value={shown.effect === 'none' ? 'Без эффекта' : EFFECTS[shown.effect].label}
          sub={EFFECTS[shown.effect].emoji}
          stopped={stopped >= 3}
        />
      </div>
      <div className="mt-5 flex gap-2">
        <Button variant="primary" size="lg" className="flex-1" onClick={go} disabled={!done}>
          <Play size={18} fill="currentColor" /> Играть
        </Button>
        <Button size="lg" onClick={roll} disabled={!done}>
          <Dices size={18} /> Ещё раз
        </Button>
      </div>
    </Modal>
  )
}
