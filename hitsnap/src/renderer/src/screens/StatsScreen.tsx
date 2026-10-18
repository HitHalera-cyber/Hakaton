import { motion } from 'framer-motion'
import { Card, cx, SectionTitle, Stat } from '@/components/ui'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { formatDate, formatNumber } from '@/lib/format'
import { MODE_INFO, STAGES } from '@/lib/game'
import { useStats } from '@/store/stats'

export function StatsScreen() {
  const s = useStats()
  const accuracy = s.totals.rounds ? Math.round((s.totals.wins / s.totals.rounds) * 100) : 0
  const avgSec = s.totals.wins ? s.totals.guessMs / s.totals.wins / 1000 : 0
  const max = Math.max(1, ...s.stageHist)
  const labels = [...STAGES.normal.map((x, i) => `${i + 1}-я попытка (${x} с)`), 'Не угадано']
  const unlocked = ACHIEVEMENTS.filter((a) => s.achievements[a.id]).length

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-black tracking-tight">Статистика</h1>
      <p className="mb-6 mt-1 text-muted">Как хорошо вы знаете музыку — в цифрах.</p>

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Игр сыграно" value={formatNumber(s.totals.games)} />
        <Stat label="Угадано песен" value={formatNumber(s.totals.wins)} hint={`из ${formatNumber(s.totals.rounds)}`} />
        <Stat label="Точность" value={`${accuracy}%`} />
        <Stat label="Лучшая серия" value={s.bestStreak} hint={avgSec ? `в среднем ${avgSec.toFixed(1).replace('.', ',')} с на ответ` : undefined} />
      </div>

      <div className="mb-8 grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <SectionTitle>С какой попытки угадываете</SectionTitle>
          <div className="space-y-3">
            {s.stageHist.map((n, i) => (
              <div key={i}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted">{labels[i]}</span>
                  <span className="font-semibold tabular-nums">{n}</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-fg/5">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(n / max) * 100}%` }}
                    transition={{ duration: 0.6, delay: i * 0.08 }}
                    className={cx('h-full rounded-full', i < 3 ? 'bg-gradient-accent' : 'bg-bad/50')}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <SectionTitle>Рекорды</SectionTitle>
          <div className="space-y-3">
            {(['classic', 'survival', 'daily'] as const).map((m) => (
              <div key={m} className="flex items-center justify-between rounded-xl bg-fg/[0.03] px-4 py-3">
                <span className="font-medium">{MODE_INFO[m].title}</span>
                <span className="text-lg font-bold tabular-nums">{s.bestScore[m] ? formatNumber(s.bestScore[m]!) : '—'}</span>
              </div>
            ))}
            <div className="flex items-center justify-between rounded-xl bg-fg/[0.03] px-4 py-3">
              <span className="font-medium">Дней с «Песней дня»</span>
              <span className="text-lg font-bold tabular-nums">{Object.keys(s.daily).length}</span>
            </div>
          </div>
        </Card>
      </div>

      <SectionTitle hint={`${unlocked} из ${ACHIEVEMENTS.length}`}>Достижения</SectionTitle>
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {ACHIEVEMENTS.map((a) => {
          const at = s.achievements[a.id]
          return (
            <Card key={a.id} className={cx('p-4 transition', !at && 'opacity-45 grayscale')}>
              <div className="text-3xl">{a.icon}</div>
              <div className="mt-2 text-sm font-semibold">{a.title}</div>
              <div className="mt-0.5 text-xs text-muted">{a.description}</div>
              {at && <div className="mt-2 text-[11px] text-accent">{new Date(at).toLocaleDateString('ru-RU')}</div>}
            </Card>
          )
        })}
      </div>

      <SectionTitle>История игр</SectionTitle>
      <Card className="divide-y divide-line">
        {s.history.length === 0 && <div className="p-6 text-center text-sm text-muted">Сыграйте первую игру — здесь появится история.</div>}
        {s.history.slice(0, 30).map((g) => (
          <div key={g.id} className="flex items-center gap-4 px-5 py-3">
            <span className="w-28 font-medium">{MODE_INFO[g.mode].title}</span>
            <span className="flex-1 text-sm text-muted">{formatDate(g.date)}</span>
            <span className="text-sm text-muted">
              {g.correct}/{g.total}
            </span>
            <span className="w-24 text-right font-bold tabular-nums">{formatNumber(g.score)}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
