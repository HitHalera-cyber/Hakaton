import { motion } from 'framer-motion'
import { Check, Target } from 'lucide-react'
import { formatNumber } from '@/lib/format'
import { questsFor } from '@/lib/quests'
import { todayKey } from '@/lib/random'
import { useStats } from '@/store/stats'
import { Card, cx } from './ui'

/** Today's three quests with progress; they reset at midnight. */
export function QuestsCard() {
  const day = todayKey()
  const questDay = useStats((s) => s.questDay)
  const progress = useStats((s) => s.questProgress)
  const done = useStats((s) => s.questsDone)
  const today = questDay === day
  const quests = questsFor(day)
  const finished = quests.filter((q) => today && done.includes(q.id)).length

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold">
          <Target size={18} className="text-accent" /> Задания дня
        </div>
        <span className="text-xs text-muted">
          {finished}/{quests.length} выполнено · обновятся в полночь
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {quests.map((q, i) => {
          const isDone = today && done.includes(q.id)
          const value = Math.min(q.target, today ? (progress[q.id] ?? 0) : 0)
          return (
            <motion.div
              key={q.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={cx('rounded-2xl border p-4', isDone ? 'border-good/40 bg-good/10' : 'border-line bg-fg/[0.02]')}
            >
              <div className="flex items-start gap-2">
                <span className={cx('mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full', isDone ? 'bg-good text-white' : 'bg-fg/10')}>
                  {isDone && <Check size={13} />}
                </span>
                <span className={cx('text-sm font-medium leading-snug', isDone && 'text-good')}>{q.title}</span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-fg/10">
                <motion.div
                  className={cx('h-full rounded-full', isDone ? 'bg-good' : 'bg-gradient-accent')}
                  initial={{ width: 0 }}
                  animate={{ width: `${(value / q.target) * 100}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-muted">
                <span className="tabular-nums">
                  {value}/{q.target}
                </span>
                <span>+{formatNumber(q.reward)} опыта</span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </Card>
  )
}
