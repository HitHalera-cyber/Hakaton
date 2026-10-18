import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import { formatNumber, plural } from '@/lib/format'
import { MODE_INFO, STATION_MODES, type GameMode } from '@/lib/game'
import { launch, type LaunchOptions } from '@/store/launch'
import { useSettings } from '@/store/settings'
import { BotPicker } from './BotPicker'
import { MODE_ICONS } from './modeIcons'
import { cx } from './ui'

/** A collection the player clicked: what it is and how to start it. */
export interface PlayTarget {
  title: string
  emoji: string
  from: string
  to: string
  count: number
  opts: LaunchOptions
}

/** «Как играть?» — picks the mode for a genre, era, playlist or personal collection. */
export function PlayModeModal({ target, onClose }: { target: PlayTarget | null; onClose: () => void }) {
  const last = useSettings((s) => s.stationMode)
  const update = useSettings((s) => s.update)

  useEffect(() => {
    if (!target) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [target, onClose])

  const start = (mode: GameMode) => {
    if (!target) return
    update({ stationMode: mode })
    onClose()
    launch(mode, target.opts)
  }

  return (
    <AnimatePresence>
      {target && (
        <motion.div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            role="dialog"
            aria-label="Как играть?"
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            className="w-full max-w-2xl overflow-hidden rounded-3xl border border-line bg-surface-2 shadow-2xl"
          >
            <div className="relative overflow-hidden p-6 text-white" style={{ background: `linear-gradient(135deg, ${target.from}, ${target.to})` }}>
              <span className="absolute -bottom-6 right-6 text-8xl opacity-30">{target.emoji}</span>
              <button onClick={onClose} className="absolute right-4 top-4 rounded-lg p-1.5 text-white/80 hover:bg-white/15 cursor-pointer" aria-label="Закрыть">
                <X size={18} />
              </button>
              <div className="relative text-xs font-semibold uppercase tracking-wider text-white/75">Как играть?</div>
              <div className="relative mt-1 text-2xl font-black">{target.title}</div>
              <div className="relative mt-1 text-sm text-white/85">
                {formatNumber(target.count)} {plural(target.count, 'песня', 'песни', 'песен')}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 p-5 sm:grid-cols-4">
              {STATION_MODES.map((m) => {
                const Icon = MODE_ICONS[m]
                return (
                  <button
                    key={m}
                    onClick={() => start(m)}
                    className={cx(
                      'flex flex-col items-start rounded-2xl border p-3 text-left transition cursor-pointer hover:-translate-y-0.5',
                      last === m ? 'border-accent bg-accent/10' : 'border-line hover:border-accent/50 hover:bg-fg/5'
                    )}
                  >
                    <span className="bg-gradient-accent mb-2 flex h-9 w-9 items-center justify-center rounded-xl text-white">
                      <Icon size={17} />
                    </span>
                    <span className="text-sm font-semibold">{MODE_INFO[m].title}</span>
                    <span className="mt-0.5 text-[11px] leading-snug text-muted">{MODE_INFO[m].subtitle}</span>
                  </button>
                )
              })}
            </div>
            <div className="border-t border-line px-5 py-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Соперник в «Дуэли»</div>
              <BotPicker />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
