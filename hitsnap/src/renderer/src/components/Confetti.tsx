import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { useUi } from '@/store/ui'

const COLORS = ['#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#0ea5e9', '#f43f5e', '#facc15']
const PIECES = 90

/** A burst of confetti over the window each time `useUi().celebrate()` is called. */
export function Confetti() {
  const burst = useUi((s) => s.confetti)
  const pieces = useMemo(
    () =>
      Array.from({ length: PIECES }, (_, i) => ({
        id: `${burst}-${i}`,
        x: 50 + (Math.random() - 0.5) * 30,
        dx: (Math.random() - 0.5) * 110,
        dy: 60 + Math.random() * 50,
        rotate: (Math.random() - 0.5) * 900,
        delay: Math.random() * 0.15,
        size: 6 + Math.random() * 7,
        round: Math.random() < 0.3,
        color: COLORS[i % COLORS.length]
      })),
    [burst]
  )
  if (!burst) return null
  return (
    <div key={burst} className="pointer-events-none fixed inset-0 z-50 overflow-hidden" aria-hidden>
      {pieces.map((p) => (
        <motion.span
          key={p.id}
          className="absolute top-[35%]"
          style={{
            left: `${p.x}%`,
            width: p.size,
            height: p.round ? p.size : p.size * 0.45,
            background: p.color,
            borderRadius: p.round ? '50%' : 2
          }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
          animate={{ x: `${p.dx}vw`, y: [`0vh`, `-${p.dy * 0.45}vh`, `${p.dy}vh`], opacity: [1, 1, 0], rotate: p.rotate }}
          transition={{ duration: 1.9, delay: p.delay, ease: 'easeOut', times: [0, 0.3, 1] }}
        />
      ))}
    </div>
  )
}
