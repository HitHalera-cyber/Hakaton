import { useMemo } from 'react'
import { plural } from '@/lib/format'
import { todayKey } from '@/lib/random'

const WEEKS = 52
const DAY_NAMES = ['Пн', '', 'Ср', '', 'Пт', '', '']

/** GitHub-style grid: rounds played per day over the last year. */
export function ActivityCalendar({ activity }: { activity: Record<string, number> }) {
  const { columns, months, max, total, days } = useMemo(() => {
    const today = new Date()
    const start = new Date(today)
    // Start on the Monday WEEKS-1 weeks ago.
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7) - (WEEKS - 1) * 7)
    const columns: Array<Array<{ key: string; count: number; future: boolean }>> = []
    const months: Array<{ col: number; label: string }> = []
    let max = 0
    let total = 0
    let days = 0
    const d = new Date(start)
    for (let w = 0; w < WEEKS; w++) {
      const col = []
      for (let i = 0; i < 7; i++) {
        const key = todayKey(d)
        const count = activity[key] ?? 0
        const future = d > today
        if (!future) {
          max = Math.max(max, count)
          total += count
          if (count) days++
        }
        const lastCol = months.length ? months[months.length - 1].col : -10
        if ((d.getDate() === 1 || (w === 0 && i === 0)) && w - lastCol >= 3) months.push({ col: w, label: d.toLocaleDateString('ru-RU', { month: 'short' }) })
        col.push({ key, count, future })
        d.setDate(d.getDate() + 1)
      }
      columns.push(col)
    }
    return { columns, months, max, total, days }
  }, [activity])

  const level = (n: number) => (n === 0 ? 0 : Math.min(4, Math.ceil((n / Math.max(max, 1)) * 4)))
  const opacity = [0, 0.3, 0.5, 0.75, 1]

  return (
    <div>
      <div className="mb-3 text-sm text-muted">
        {total} {plural(total, 'раунд', 'раунда', 'раундов')} за год · активных дней: {days}
      </div>
      <div className="flex gap-2 overflow-x-auto">
        <div className="mt-5 flex flex-col gap-[3px] text-[10px] text-muted">
          {DAY_NAMES.map((n, i) => (
            <div key={i} className="h-3 leading-3">
              {n}
            </div>
          ))}
        </div>
        <div>
          <div className="relative mb-1 h-4 text-[10px] text-muted">
            {months.map((m) => (
              <span key={`${m.col}-${m.label}`} className="absolute" style={{ left: m.col * 15 }}>
                {m.label}
              </span>
            ))}
          </div>
          <div className="flex gap-[3px]">
            {columns.map((col, w) => (
              <div key={w} className="flex flex-col gap-[3px]">
                {col.map((c) => (
                  <div
                    key={c.key}
                    title={c.future ? '' : `${c.key.split('-').reverse().join('.')}: ${c.count} ${plural(c.count, 'раунд', 'раунда', 'раундов')}`}
                    className="h-3 w-3 rounded-[3px]"
                    style={{
                      background: c.future ? 'transparent' : c.count ? 'var(--accent)' : 'color-mix(in oklab, var(--fg) 8%, transparent)',
                      opacity: c.count ? opacity[level(c.count)] : 1
                    }}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
