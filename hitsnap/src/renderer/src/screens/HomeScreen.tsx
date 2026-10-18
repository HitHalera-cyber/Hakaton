import { motion } from 'framer-motion'
import { CalendarDays, Dices, Flame, Play, Radio, Swords, Trophy } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Genre, Lang } from '@shared/types'
import { BotPicker } from '@/components/BotPicker'
import { ChallengeModal } from '@/components/ChallengeModal'
import { LevelBadge } from '@/components/LevelBadge'
import { Modal } from '@/components/Modal'
import { MODE_ICONS } from '@/components/modeIcons'
import { Roulette } from '@/components/Roulette'
import { LogoMark } from '@/components/Logo'
import { PartySetup } from '@/components/PartySetup'
import { QuestsCard } from '@/components/QuestsCard'
import { Button, Card, Chip, cx, SectionTitle, Segmented, Stat } from '@/components/ui'
import { EFFECTS, type SoundEffect } from '@/lib/audio'
import { formatNumber, formatSeconds, plural } from '@/lib/format'
import {
  GENRE_LABELS,
  LANG_LABELS,
  matchesFilters,
  MODE_INFO,
  POPULARITY_INFO,
  STAGES,
  type ClipStart,
  type Difficulty,
  type GameMode,
  type Popularity
} from '@/lib/game'
import { dailyStreak } from '@/lib/progress'
import { todayKey } from '@/lib/random'
import { daysLeftInWeek, weeklyChallenge, WEEKLY_ROUNDS } from '@/lib/weekly'
import { useUi } from '@/store/ui'
import { launch, launchWeekly } from '@/store/launch'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'

const DECADES = [1960, 1970, 1980, 1990, 2000, 2010, 2020]

const MODES: GameMode[] = ['classic', 'survival', 'blitz', 'duel', 'quiz', 'artist', 'year', 'daily', 'party', 'practice']

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item]
}

export function HomeScreen() {
  const settings = useSettings()
  const songs = useAllSongs()
  const stats = useStats()
  const [partyOpen, setPartyOpen] = useState(false)
  const [duelOpen, setDuelOpen] = useState(false)
  const [rouletteOpen, setRouletteOpen] = useState(false)
  const [challengeOpen, setChallengeOpen] = useState(false)
  const go = useUi((u) => u.go)
  const week = weeklyChallenge()
  const weekResult = stats.weekly?.[week.key]
  const daysLeft = daysLeftInWeek()
  const today = todayKey()
  const dailyResult = stats.daily[today]
  const streak = dailyStreak(Object.keys(stats.daily))

  const f = settings.filters
  const popularity = f.popularity ?? 'all'
  const filtered = useMemo(() => songs.filter((s) => matchesFilters(s, f)), [songs, f])
  const setFilters = (patch: Partial<typeof f>) => settings.update({ filters: { ...f, ...patch } })
  const anyFilter = f.decades.length || f.genres.length || f.langs.length

  const play = (mode: GameMode) => (mode === 'party' ? setPartyOpen(true) : mode === 'duel' ? setDuelOpen(true) : launch(mode))

  const accuracy = stats.totals.rounds ? Math.round((stats.totals.wins / stats.totals.rounds) * 100) : 0
  const stages = STAGES[settings.difficulty]

  return (
    <div className="mx-auto max-w-5xl">
      <motion.section initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="relative mb-8 overflow-hidden rounded-3xl p-8">
        <div className="bg-gradient-accent absolute inset-0 opacity-90" />
        <div className="absolute -right-10 -top-10 opacity-20">
          <LogoMark size={260} />
        </div>
        <div className="relative flex items-end justify-between gap-6 text-white">
          <div>
            <h1 className="text-4xl font-black tracking-tight">Узнаете хит за секунду?</h1>
            <p className="mt-2 max-w-xl text-white/85">
              Слушайте {stages.map(formatSeconds).join(', затем ')} — и найдите песню в поиске. Чем раньше угадаете, тем больше очков.
              В базе {formatNumber(songs.length)} {plural(songs.length, 'песня', 'песни', 'песен')}.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button size="lg" className="bg-white! text-black! shadow-xl hover:brightness-95" onClick={() => launch('classic')}>
                <Play size={18} fill="currentColor" /> Быстрая игра
              </Button>
              <Button size="lg" variant="ghost" className="border border-white/40 bg-white/10 text-white! hover:bg-white/20!" onClick={() => launch('daily')}>
                <CalendarDays size={18} /> {dailyResult ? `Песня дня: ${dailyResult.correct}/${dailyResult.total}` : 'Песня дня'}
              </Button>
            </div>
          </div>
          <div className="hidden shrink-0 flex-col items-end gap-3 lg:flex">
            <div className="rounded-2xl bg-white/15 px-4 py-3 backdrop-blur [&_.text-muted]:text-white/75 [&_.text-fg\/10]:text-white/20">
              <LevelBadge />
            </div>
            {streak > 0 && (
              <div className="flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-sm font-semibold backdrop-blur" title="Дней подряд с «Песней дня»">
                <Flame size={16} /> {streak} {plural(streak, 'день', 'дня', 'дней')} подряд
              </div>
            )}
          </div>
        </div>
      </motion.section>

      <SectionTitle>Режимы</SectionTitle>
      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {MODES.map((mode, i) => {
          const Icon = MODE_ICONS[mode]
          const best = stats.bestScore[mode]
          return (
            <motion.button
              key={mode}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 * i }}
              whileHover={{ y: -3 }}
              onClick={() => play(mode)}
              className="glass group flex flex-col rounded-2xl p-5 text-left transition hover:border-accent/50 cursor-pointer"
            >
              <span className="bg-gradient-accent mb-4 flex h-11 w-11 items-center justify-center rounded-xl text-white shadow-lg shadow-accent/30">
                <Icon size={20} />
              </span>
              <span className="font-semibold">{MODE_INFO[mode].title}</span>
              <span className="mt-1 text-sm text-muted">{MODE_INFO[mode].subtitle}</span>
              <span className="mt-auto pt-4 text-xs text-muted">
                {mode === 'daily'
                  ? dailyResult
                    ? `Сегодня: ${formatNumber(dailyResult.score)} очков`
                    : 'Ещё не сыграно сегодня'
                  : mode === 'practice'
                    ? 'Результаты не идут в рекорды'
                    : mode === 'duel'
                      ? best
                        ? `Рекорд: ${formatNumber(best)}`
                        : 'Выберите соперника'
                    : mode === 'party'
                      ? `${settings.players.length} ${plural(settings.players.length, 'игрок', 'игрока', 'игроков')} · ${settings.partyRounds} раундов`
                      : best
                        ? `Рекорд: ${formatNumber(best)}`
                        : 'Рекорда пока нет'}
              </span>
            </motion.button>
          )
        })}
      </div>

      <SectionTitle>Ещё во что поиграть</SectionTitle>
      <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <motion.button
          whileHover={{ y: -3 }}
          onClick={launchWeekly}
          className="relative overflow-hidden rounded-2xl p-5 text-left text-white shadow-lg cursor-pointer"
          style={{ background: `linear-gradient(135deg, ${week.theme.from}, ${week.theme.to})` }}
        >
          <span className="absolute -bottom-4 -right-1 text-7xl opacity-30">{week.theme.emoji}</span>
          <span className="relative flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-white/80">
            <Trophy size={13} /> Испытание недели
          </span>
          <span className="relative mt-1 block text-xl font-black">{week.theme.title}</span>
          <span className="relative mt-1 block text-sm text-white/85">
            {WEEKLY_ROUNDS} песен, одинаковых для всех. Ещё {daysLeft} {plural(daysLeft, 'день', 'дня', 'дней')}.
          </span>
          <span className="relative mt-3 inline-block rounded-full bg-white/20 px-3 py-1 text-xs font-semibold backdrop-blur">
            {weekResult ? `Лучший результат: ${weekResult.correct}/${weekResult.total} · ${formatNumber(weekResult.score)}` : 'Ещё не пройдено'}
          </span>
        </motion.button>
        <motion.button
          whileHover={{ y: -3 }}
          onClick={() => setRouletteOpen(true)}
          className="relative overflow-hidden rounded-2xl p-5 text-left text-white shadow-lg cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #475569, #7c3aed)' }}
        >
          <span className="absolute -bottom-4 -right-1 text-7xl opacity-30">🎰</span>
          <span className="relative flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-white/80">
            <Dices size={13} /> Рулетка
          </span>
          <span className="relative mt-1 block text-xl font-black">Испытай удачу</span>
          <span className="relative mt-1 block text-sm text-white/85">Случайный режим, жанр и звуковой эффект — играем то, что выпало.</span>
        </motion.button>
        <motion.button
          whileHover={{ y: -3 }}
          onClick={() => go('radio')}
          className="relative overflow-hidden rounded-2xl p-5 text-left text-white shadow-lg cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #0ea5e9, #16a34a)' }}
        >
          <span className="absolute -bottom-4 -right-1 text-7xl opacity-30">📻</span>
          <span className="relative flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-white/80">
            <Radio size={13} /> Радио
          </span>
          <span className="relative mt-1 block text-xl font-black">Слушай и угадывай</span>
          <span className="relative mt-1 block text-sm text-white/85">Песни идут подряд, название скрыто — угадывайте вслух, без очков и спешки.</span>
        </motion.button>
        <motion.button
          whileHover={{ y: -3 }}
          onClick={() => setChallengeOpen(true)}
          className="relative overflow-hidden rounded-2xl p-5 text-left text-white shadow-lg cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #f43f5e, #7c3aed)' }}
        >
          <span className="absolute -bottom-4 -right-1 text-7xl opacity-30">⚔️</span>
          <span className="relative flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-white/80">
            <Swords size={13} /> Вызов другу
          </span>
          <span className="relative mt-1 block text-xl font-black">Кто знает больше?</span>
          <span className="relative mt-1 block text-sm text-white/85">Сыграйте и отправьте код — друг услышит те же песни и сравнит результат.</span>
        </motion.button>
      </div>

      <div className="mb-8">
        <QuestsCard />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card className="p-6">
          <SectionTitle hint={`${formatNumber(filtered.length)} ${plural(filtered.length, 'песня', 'песни', 'песен')} в игре`}>
            Какие песни загадывать
          </SectionTitle>
          <div className="space-y-5">
            <div>
              <div className="mb-2 text-sm font-medium">Известность</div>
              <Segmented<Popularity>
                value={popularity}
                onChange={(p) => setFilters({ popularity: p })}
                options={(Object.keys(POPULARITY_INFO) as Popularity[]).map((p) => ({ value: p, label: POPULARITY_INFO[p].label }))}
              />
              <div className="mt-1.5 text-xs text-muted">{POPULARITY_INFO[popularity].hint}</div>
            </div>
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
            <div className={cx('text-xs text-muted', !anyFilter && 'invisible')}>
              <button
                className="underline-offset-2 hover:text-fg hover:underline cursor-pointer"
                onClick={() => setFilters({ decades: [], genres: [], langs: [] })}
              >
                Сбросить фильтры
              </button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="mb-3 text-sm font-medium">Длина отрывков</div>
            <Segmented<Difficulty>
              value={settings.difficulty}
              onChange={(difficulty) => settings.update({ difficulty })}
              options={[
                { value: 'easy', label: 'Лёгкая' },
                { value: 'normal', label: 'Обычная' },
                { value: 'hard', label: 'Хардкор' }
              ]}
            />
            <div className="mt-2 text-xs text-muted">{stages.map(formatSeconds).join(' → ')}</div>
          </Card>
          <Card className="p-5">
            <div className="mb-3 text-sm font-medium">Откуда звучит отрывок</div>
            <Segmented<ClipStart>
              value={settings.clipStart}
              onChange={(clipStart) => settings.update({ clipStart })}
              options={[
                { value: 'random', label: 'Случайный момент' },
                { value: 'intro', label: 'С начала' }
              ]}
            />
            <div className="mt-2 text-xs leading-relaxed text-muted">
              {settings.clipStart === 'intro'
                ? 'Отрывок играет с первой ноты записи. Для своей музыки это настоящее начало песни, для базы — начало 30-секундного фрагмента от Deezer.'
                : 'Отрывок берётся из случайного места — часто это припев или самый узнаваемый момент.'}
            </div>
          </Card>
          <Card className="p-5">
            <div className="mb-3 flex items-baseline justify-between">
              <span className="text-sm font-medium">Звуковой эффект</span>
              {settings.effect !== 'none' && <span className="text-xs font-semibold text-accent">очки ×{EFFECTS[settings.effect].bonus}</span>}
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              {(Object.keys(EFFECTS) as SoundEffect[]).map((e) => (
                <button
                  key={e}
                  onClick={() => settings.update({ effect: e })}
                  title={`${EFFECTS[e].label}: ${EFFECTS[e].hint}`}
                  className={cx(
                    'flex h-11 items-center justify-center rounded-xl border text-xl transition cursor-pointer',
                    settings.effect === e ? 'border-accent bg-accent/12 shadow' : 'border-line hover:bg-fg/5'
                  )}
                >
                  {EFFECTS[e].emoji}
                </button>
              ))}
            </div>
            <div className="mt-2 text-xs text-muted">
              {EFFECTS[settings.effect].label} — {EFFECTS[settings.effect].hint.toLowerCase()}
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-4">
            <Stat label="Угадано" value={formatNumber(stats.totals.wins)} hint={`точность ${accuracy}%`} />
            <Stat label="Серия" value={stats.bestStreak} hint="лучшая" />
          </div>
        </div>
      </div>
      <PartySetup open={partyOpen} onClose={() => setPartyOpen(false)} />
      <Roulette open={rouletteOpen} onClose={() => setRouletteOpen(false)} />
      <ChallengeModal open={challengeOpen} onClose={() => setChallengeOpen(false)} />
      <Modal open={duelOpen} onClose={() => setDuelOpen(false)} title="Дуэль с ботом">
        <p className="-mt-2 mb-4 text-sm text-muted">
          Вы и бот слушаете одни и те же отрывки. Кто узнал песню на более короткой попытке, тот выиграл раунд. Выберите соперника:
        </p>
        <BotPicker
          onPick={() => {
            setDuelOpen(false)
            launch('duel')
          }}
        />
      </Modal>
    </div>
  )
}
