import { motion } from 'framer-motion'
import { Flame } from 'lucide-react'
import { useMemo } from 'react'
import type { Genre } from '@shared/types'
import { LevelBadge } from '@/components/LevelBadge'
import { Card, cx, SectionTitle, Stat } from '@/components/ui'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { formatDate, formatNumber, plural } from '@/lib/format'
import { GENRE_LABELS, GENRE_STYLE, MODE_INFO, STAGES } from '@/lib/game'
import { dailyStreak, levelFor, pointsForLevel } from '@/lib/progress'
import { useAllSongs } from '@/store/library'
import { useStats } from '@/store/stats'

/** Accuracy per genre, from per-song results. */
function useGenreStats() {
  const songs = useAllSongs()
  const stats = useStats((s) => s.songs)
  return useMemo(() => {
    const genreOf = new Map(songs.map((s) => [s.id, s.genre]))
    const acc: Partial<Record<Genre, { played: number; won: number }>> = {}
    for (const [id, st] of Object.entries(stats)) {
      const g = genreOf.get(id)
      if (!g) continue
      const a = (acc[g] ??= { played: 0, won: 0 })
      a.played += st.played
      a.won += st.won
    }
    return (Object.entries(acc) as Array<[Genre, { played: number; won: number }]>)
      .filter(([, a]) => a.played > 0)
      .sort((a, b) => b[1].won / b[1].played - a[1].won / a[1].played || b[1].played - a[1].played)
  }, [songs, stats])
}

export function StatsScreen() {
  const s = useStats()
  const accuracy = s.totals.rounds ? Math.round((s.totals.wins / s.totals.rounds) * 100) : 0
  const avgSec = s.totals.wins ? s.totals.guessMs / s.totals.wins / 1000 : 0
  const max = Math.max(1, ...s.stageHist)
  const labels = [...STAGES.normal.map((x, i) => `${i + 1}-я попытка (${x} с)`), 'Не угадано']
  const unlocked = ACHIEVEMENTS.filter((a) => s.achievements[a.id]).length
  const genres = useGenreStats()
  const lvl = levelFor(s.totals.points ?? 0)
  const streak = dailyStreak(Object.keys(s.daily))

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-black tracking-tight">Статистика</h1>
      <p className="mb-6 mt-1 text-muted">Как хорошо вы знаете музыку — в цифрах.</p>

      <Card className="mb-6 flex flex-wrap items-center gap-6 p-6">
        <LevelBadge />
        <div className="min-w-60 flex-1">
          <div className="mb-1.5 flex justify-between text-sm">
            <span className="text-muted">До уровня {lvl.level + 1}</span>
            <span className="font-semibold tabular-nums">
              {formatNumber(Math.max(0, (s.totals.points ?? 0) - pointsForLevel(lvl.level)))} / {formatNumber(pointsForLevel(lvl.level + 1) - pointsForLevel(lvl.level))}
            </span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-fg/10">
            <motion.div initial={{ width: 0 }} animate={{ width: `${lvl.progress * 100}%` }} transition={{ duration: 0.8 }} className="bg-gradient-accent h-full rounded-full" />
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-2xl bg-warn/10 px-4 py-3 text-warn" title="Дней подряд с «Песней дня»">
          <Flame size={22} />
          <div className="leading-tight">
            <div className="text-xl font-bold tabular-nums">{streak}</div>
            <div className="text-xs">{plural(streak, 'день', 'дня', 'дней')} подряд</div>
          </div>
        </div>
      </Card>

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
            {(['classic', 'survival', 'quiz', 'year', 'daily'] as const).map((m) => (
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

      <SectionTitle>Жанры</SectionTitle>
      <Card className="mb-8 p-6">
        {genres.length === 0 ? (
          <div className="text-center text-sm text-muted">Сыграйте несколько раундов — здесь появится, в каких жанрах вы сильнее.</div>
        ) : (
          <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
            {genres.map(([g, a], i) => {
              const pct = Math.round((a.won / a.played) * 100)
              return (
                <div key={g} className="flex items-center gap-3 text-sm">
                  <span className="w-6 text-center text-lg">{GENRE_STYLE[g].emoji}</span>
                  <span className="w-36 shrink-0 truncate">{GENRE_LABELS[g]}</span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-fg/5">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: i * 0.04 }}
                      className="h-full rounded-full"
                      style={{ background: `linear-gradient(90deg, ${GENRE_STYLE[g].from}, ${GENRE_STYLE[g].to})` }}
                    />
                  </div>
                  <span className="w-20 text-right tabular-nums text-muted">
                    {pct}% · {a.won}/{a.played}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </Card>

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
            <span className="w-44 truncate font-medium" title={g.label}>
              {MODE_INFO[g.mode].title}
              {g.label && <span className="font-normal text-muted"> · {g.label}</span>}
            </span>
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
