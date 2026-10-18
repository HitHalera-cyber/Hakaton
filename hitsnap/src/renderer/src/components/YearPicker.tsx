import { Minus, Plus, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { YEAR_RANGE } from '@/lib/game'
import { Button, Kbd } from './ui'

/** Year mode answer: a big number, a slider and ±1 buttons; ←/→ and Enter work too. */
export function YearPicker({ onSubmit, disabled }: { onSubmit: (year: number) => void; disabled?: boolean }) {
  const [year, setYear] = useState(1995)
  const clamp = (y: number) => Math.min(YEAR_RANGE.max, Math.max(YEAR_RANGE.min, y))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (disabled || e.target instanceof HTMLInputElement) return
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') setYear((y) => clamp(y - (e.shiftKey ? 10 : 1)))
      else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') setYear((y) => clamp(y + (e.shiftKey ? 10 : 1)))
      else if (e.key === 'Enter') onSubmit(year)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [year, disabled, onSubmit])

  const decades = []
  for (let d = Math.ceil(YEAR_RANGE.min / 10) * 10; d <= YEAR_RANGE.max; d += 10) decades.push(d)

  return (
    <div className="glass rounded-2xl p-6">
      <div className="flex items-center justify-center gap-6">
        <button onClick={() => setYear((y) => clamp(y - 1))} className="flex h-12 w-12 items-center justify-center rounded-full bg-fg/5 text-muted transition hover:bg-accent/15 hover:text-accent cursor-pointer" aria-label="На год раньше">
          <Minus size={20} />
        </button>
        <div className="text-gradient w-44 text-center text-7xl font-black tabular-nums tracking-tight">{year}</div>
        <button onClick={() => setYear((y) => clamp(y + 1))} className="flex h-12 w-12 items-center justify-center rounded-full bg-fg/5 text-muted transition hover:bg-accent/15 hover:text-accent cursor-pointer" aria-label="На год позже">
          <Plus size={20} />
        </button>
      </div>
      <input
        type="range"
        min={YEAR_RANGE.min}
        max={YEAR_RANGE.max}
        value={year}
        onChange={(e) => setYear(Number(e.target.value))}
        className="mt-6 w-full"
        aria-label="Год"
      />
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        {decades.map((d) => (
          <button key={d} onClick={() => setYear(d)} className="hover:text-fg cursor-pointer">
            {d}
          </button>
        ))}
      </div>
      <div className="mt-5 flex items-center justify-between">
        <span className="text-xs text-muted">
          <Kbd>←</Kbd> <Kbd>→</Kbd> год · <Kbd>Shift</Kbd> десятилетие
        </span>
        <Button variant="primary" size="lg" onClick={() => onSubmit(year)} disabled={disabled}>
          <Send size={16} /> Ответить
        </Button>
      </div>
    </div>
  )
}
