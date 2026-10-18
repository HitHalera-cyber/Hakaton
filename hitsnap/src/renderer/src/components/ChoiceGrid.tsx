import { motion } from 'framer-motion'
import { useEffect } from 'react'
import type { Song } from '@shared/types'
import { Kbd, cx } from './ui'

/** Quiz answers: four big buttons, keys 1–4. Wrong picks stay crossed out. */
export function ChoiceGrid({ options, wrongIds, onPick }: { options: Song[]; wrongIds: string[]; onPick: (song: Song) => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      const i = Number(e.key) - 1
      const song = options[i]
      if (song && !wrongIds.includes(song.id)) {
        e.preventDefault()
        onPick(song)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [options, wrongIds, onPick])

  return (
    <div className="grid grid-cols-2 gap-3">
      {options.map((song, i) => {
        const wrong = wrongIds.includes(song.id)
        return (
          <motion.button
            key={song.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            whileHover={wrong ? undefined : { y: -2 }}
            disabled={wrong}
            onClick={() => onPick(song)}
            className={cx(
              'flex items-center gap-3 rounded-2xl border p-4 text-left backdrop-blur-xl transition cursor-pointer',
              wrong ? 'pointer-events-none border-bad/40 bg-bad/10 opacity-50' : 'border-line bg-surface hover:border-accent/60 hover:bg-accent/5'
            )}
          >
            <Kbd>{i + 1}</Kbd>
            <span className="min-w-0 flex-1">
              <span className={cx('block truncate font-semibold', wrong && 'line-through')}>{song.title}</span>
              <span className="block truncate text-sm text-muted">{song.artist}</span>
            </span>
          </motion.button>
        )
      })}
    </div>
  )
}
