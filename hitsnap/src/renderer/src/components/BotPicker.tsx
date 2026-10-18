import type { BotLevel } from '@/lib/game'
import { BOT_LEVELS } from '@/lib/game'
import { useSettings } from '@/store/settings'
import { cx } from './ui'

/** Three cards to choose the duel opponent. */
export function BotPicker({ onPick }: { onPick?: (level: BotLevel) => void }) {
  const level = useSettings((s) => s.botLevel)
  const update = useSettings((s) => s.update)
  return (
    <div className="grid grid-cols-3 gap-2">
      {(Object.keys(BOT_LEVELS) as BotLevel[]).map((l) => (
        <button
          key={l}
          onClick={() => {
            update({ botLevel: l })
            onPick?.(l)
          }}
          className={cx(
            'flex flex-col items-center rounded-2xl border p-3 text-center transition cursor-pointer',
            level === l ? 'border-accent bg-accent/12 shadow' : 'border-line hover:bg-fg/5'
          )}
        >
          <span className="text-3xl">{BOT_LEVELS[l].emoji}</span>
          <span className="mt-1 text-sm font-semibold">{BOT_LEVELS[l].label}</span>
          <span className="mt-0.5 text-[11px] leading-tight text-muted">{BOT_LEVELS[l].hint}</span>
        </button>
      ))}
    </div>
  )
}
