import { motion } from 'framer-motion'
import { CalendarDays, Dumbbell, Heart, Play, Trophy } from 'lucide-react'
import type { ComponentType } from 'react'
import { useMemo } from 'react'
import { CATALOG } from '@shared/catalog'
import type { Genre, Lang } from '@shared/types'
import { Button, Card, Chip, cx, SectionTitle, Segmented, Stat } from '@/components/ui'
import { LogoMark } from '@/components/Logo'
import { formatNumber, formatSeconds, plural } from '@/lib/format'
import {
  DAILY_ROUNDS,
  GENRE_LABELS,
  LANG_LABELS,
  matchesFilters,
  MODE_INFO,
  seedFor,
  STAGES,
  type Difficulty,
  type GameMode
} from '@/lib/game'
import { todayKey } from '@/lib/random'
import { useGame } from '@/store/game'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'

const DECADES = [1960, 1970, 1980, 1990, 2000, 2010, 2020]

const MODE_ICONS: Record<GameMode, ComponentType<{ size?: number }>> = {
  classic: Trophy,
  survival: Heart,
  daily: CalendarDays,
  practice: Dumbbell
}

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item]
}

export function HomeScreen() {
  const settings = useSettings()
  const songs = useAllSongs()
  const start = useGame((s) => s.start)
  const stats = useStats()
  const today = todayKey()
  const dailyResult = stats.daily[today]

  const filtered = useMemo(() => songs.filter((s) => matchesFilters(s, settings.filters)), [songs, settings.filters])
  const f = settings.filters
  const setFilters = (patch: Partial<typeof f>) => settings.update({ filters: { ...f, ...patch } })

  const play = (mode: GameMode) => {
    const rounds = mode === 'classic' ? settings.roundsPerGame : mode === 'daily' ? DAILY_ROUNDS : Infinity
    void start(
      {
        mode,
        difficulty: settings.difficulty,
        rounds,
        filters: settings.filters,
        seed: seedFor(mode, today),
        dailyKey: mode === 'daily' ? today : undefined
      },
      mode === 'daily' ? CATALOG : songs
    )
  }

  const accuracy = stats.totals.rounds ? Math.round((stats.totals.wins / stats.totals.rounds) * 100) : 0
  const stages = STAGES[settings.difficulty]

  return (
    <div className="mx-auto max-w-5xl">
      <motion.section
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative mb-8 overflow-hidden rounded-3xl p-8"
      >
        <div className="bg-gradient-accent absolute inset-0 opacity-90" />
        <div className="absolute -right-10 -top-10 opacity-20">
          <LogoMark size={260} />
        </div>
        <div className="relative text-white">
          <h1 className="text-4xl font-black tracking-tight">Узнаете хит за секунду?</h1>
          <p className="mt-2 max-w-xl text-white/85">
            Слушайте {stages.map(formatSeconds).join(', затем ')} — и найдите песню в поиске. Чем раньше угадаете, тем больше очков.
            В базе {formatNumber(songs.length)} {plural(songs.length, 'песня', 'песни', 'песен')}.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button size="lg" className="bg-white! text-black! shadow-xl hover:brightness-95" onClick={() => play('classic')}>
              <Play size={18} fill="currentColor" /> Быстрая игра
            </Button>
            <Button size="lg" variant="ghost" className="border border-white/40 bg-white/10 text-white! hover:bg-white/20!" onClick={() => play('daily')}>
              <CalendarDays size={18} /> {dailyResult ? `Песня дня: ${dailyResult.correct}/${dailyResult.total}` : 'Песня дня'}
            </Button>
          </div>
        </div>
      </motion.section>

      <SectionTitle>Режимы</SectionTitle>
      <div className="mb-8 grid grid-cols-2 gap-4 xl:grid-cols-4">
        {(Object.keys(MODE_INFO) as GameMode[]).map((mode, i) => {
          const Icon = MODE_ICONS[mode]
          const best = stats.bestScore[mode]
          return (
            <motion.button
              key={mode}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
              whileHover={{ y: -3 }}
              onClick={() => play(mode)}
              className="glass group flex flex-col rounded-2xl p-5 text-left transition hover:border-accent/50 cursor-pointer"
            >
              <span className="bg-gradient-accent mb-4 flex h-11 w-11 items-center justify-center rounded-xl text-white shadow-lg shadow-accent/30">
                <Icon size={20} />
              </span>
              <span className="font-semibold">{MODE_INFO[mode].title}</span>
              <span className="mt-1 text-sm text-muted">{MODE_INFO[mode].subtitle}</span>
              <span className="mt-4 text-xs text-muted">
                {mode === 'daily'
                  ? dailyResult
                    ? `Сегодня: ${formatNumber(dailyResult.score)} очков`
                    : 'Ещё не сыграно сегодня'
                  : mode === 'practice'
                    ? 'Результаты не идут в рекорды'
                    : best
                      ? `Рекорд: ${formatNumber(best)}`
                      : 'Рекорда пока нет'}
              </span>
            </motion.button>
          )
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <Card className="p-6">
          <SectionTitle hint={`${formatNumber(filtered.length)} ${plural(filtered.length, 'песня', 'песни', 'песен')} в игре`}>
            Какие песни загадывать
          </SectionTitle>
          <div className="space-y-5">
            <div>
              <div className="mb-2 text-sm font-medium">Десятилетия</div>
              <div className="flex flex-wrap gap-2">
                {DECADES.map((d) => (
                  <Chip key={d} active={f.decades.includes(d)} onClick={() => setFilters({ decades: toggle(f.decades, d) })}>
                    {d === 1960 ? '60-е и раньше' : `${String(d).slice(2)}-е`}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Жанры</div>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(GENRE_LABELS) as Genre[]).map((g) => (
                  <Chip key={g} active={f.genres.includes(g)} onClick={() => setFilters({ genres: toggle(f.genres, g) })}>
                    {GENRE_LABELS[g]}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Язык</div>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(LANG_LABELS) as Lang[]).map((l) => (
                  <Chip key={l} active={f.langs.includes(l)} onClick={() => setFilters({ langs: toggle(f.langs, l) })}>
                    {LANG_LABELS[l]}
                  </Chip>
                ))}
              </div>
            </div>
            <div className={cx('text-xs text-muted', !(f.decades.length || f.genres.length || f.langs.length) && 'invisible')}>
              <button className="underline-offset-2 hover:text-fg hover:underline cursor-pointer" onClick={() => setFilters({ decades: [], genres: [], langs: [] })}>
                Сбросить фильтры
              </button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="mb-3 text-sm font-medium">Сложность</div>
            <Segmented<Difficulty>
              value={settings.difficulty}
              onChange={(difficulty) => settings.update({ difficulty })}
              options={[
                { value: 'easy', label: 'Лёгкая' },
                { value: 'normal', label: 'Обычная' },
                { value: 'hard', label: 'Хардкор' }
              ]}
            />
            <div className="mt-3 text-xs text-muted">Отрывки: {stages.map(formatSeconds).join(' → ')}</div>
          </Card>
          <div className="grid grid-cols-2 gap-4">
            <Stat label="Угадано" value={formatNumber(stats.totals.wins)} hint={`точность ${accuracy}%`} />
            <Stat label="Серия" value={stats.bestStreak} hint="лучшая" />
          </div>
        </div>
      </div>
    </div>
  )
}
