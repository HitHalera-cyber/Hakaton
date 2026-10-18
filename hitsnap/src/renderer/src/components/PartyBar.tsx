import { motion } from 'framer-motion'
import { formatNumber } from '@/lib/format'
import type { Player } from '@/lib/game'
import { Kbd, cx } from './ui'

/** Party scoreboard; a player's chip is also their buzzer. */
export function PartyBar({
  players,
  scores,
  buzzed,
  lockedOut,
  onBuzz,
  live
}: {
  players: Player[]
  scores: number[]
  buzzed: number | null
  lockedOut: number[]
  onBuzz: (i: number) => void
  live: boolean
}) {
  const leader = Math.max(...scores)
  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${players.length}, minmax(0, 1fr))` }}>
      {players.map((p, i) => {
        const out = lockedOut.includes(i)
        const active = buzzed === i
        return (
          <motion.button
            key={i}
            onClick={() => onBuzz(i)}
            disabled={!live || out || buzzed !== null}
            animate={{ scale: active ? 1.04 : 1 }}
            className={cx(
              'relative overflow-hidden rounded-2xl border p-3 text-left transition cursor-pointer disabled:cursor-default',
              active ? 'border-transparent text-white shadow-xl' : 'glass',
              out && 'opacity-40'
            )}
            style={active ? { background: p.color, boxShadow: `0 10px 30px -10px ${p.color}` } : undefined}
          >
            <div className="flex items-center gap-2">
              {!active && <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: p.color }} />}
              <span className="truncate text-sm font-semibold">{p.name}</span>
              {scores[i] === leader && leader > 0 && <span title="Лидер">👑</span>}
              <span className="ml-auto">
                <Kbd>{i + 1}</Kbd>
              </span>
            </div>
            <div className="mt-1 text-xl font-bold tabular-nums">{formatNumber(scores[i] ?? 0)}</div>
            {active && <div className="text-xs text-white/85">отвечает…</div>}
            {out && <div className="text-xs text-muted">ошибся в этом раунде</div>}
          </motion.button>
        )
      })}
    </div>
  )
}
