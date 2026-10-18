import { Lock } from 'lucide-react'
import { formatSeconds } from '@/lib/format'
import { cx } from './ui'

/**
 * The 1 s / 3 s / 5 s ladder: segment widths follow the clip lengths, the
 * current stage fills as it plays, later stages stay locked.
 */
export function StageTimeline({
  stages,
  stage,
  elapsed,
  playing,
  finished
}: {
  stages: number[]
  stage: number
  elapsed: number
  playing: boolean
  finished?: boolean
}) {
  const total = stages[stages.length - 1]
  const current = stages[stage]
  const fill = playing ? Math.min(elapsed, current) / total : 0
  return (
    <div>
      <div className="relative h-3 overflow-hidden rounded-full bg-fg/10">
        <div className="absolute inset-y-0 left-0 bg-accent/25 transition-all duration-300" style={{ width: `${(current / total) * 100}%` }} />
        <div className="bg-gradient-accent absolute inset-y-0 left-0 rounded-full" style={{ width: `${fill * 100}%` }} />
        {stages.slice(0, -1).map((s) => (
          <div key={s} className="absolute inset-y-0 w-0.5 bg-bg" style={{ left: `${(s / total) * 100}%` }} />
        ))}
      </div>
      <div className="relative mt-2 h-5 text-xs font-medium">
        {stages.map((s, i) => (
          <span
            key={s}
            className={cx(
              'absolute flex -translate-x-full items-center gap-1 whitespace-nowrap tabular-nums transition',
              i === stage && !finished ? 'text-fg' : i < stage ? 'text-muted line-through' : 'text-muted/70'
            )}
            style={{ left: `${(s / total) * 100}%` }}
          >
            {i > stage && !finished && <Lock size={11} />}
            {formatSeconds(s)}
          </span>
        ))}
      </div>
    </div>
  )
}
