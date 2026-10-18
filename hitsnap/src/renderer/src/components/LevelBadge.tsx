import { formatNumber } from '@/lib/format'
import { levelFor } from '@/lib/progress'
import { useStats } from '@/store/stats'

/** Player level with progress to the next one. */
export function LevelBadge({ compact }: { compact?: boolean }) {
  const points = useStats((s) => s.totals.points ?? 0)
  const lvl = levelFor(points)
  const r = 18
  const c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-3" title={`До следующего уровня: ${formatNumber(lvl.toNext)} очков`}>
      <div className="relative h-11 w-11 shrink-0">
        <svg viewBox="0 0 44 44" className="absolute inset-0 -rotate-90">
          <circle cx="22" cy="22" r={r} fill="none" stroke="currentColor" strokeWidth="3.5" className="text-fg/10" />
          <circle
            cx="22"
            cy="22"
            r={r}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - lvl.progress)}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold tabular-nums">{lvl.level}</span>
      </div>
      {!compact && (
        <div className="min-w-0 leading-tight">
          <div className="truncate text-sm font-semibold">{lvl.title}</div>
          <div className="text-xs text-muted">{formatNumber(points)} очков</div>
        </div>
      )}
    </div>
  )
}
