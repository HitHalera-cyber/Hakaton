import { motion } from 'framer-motion'
import { FolderOpen, Heart, Link2, Loader2, Play, RefreshCw, RotateCcw, Trash2, TrendingUp, Music2 } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import type { Genre, Song } from '@shared/types'
import { PlayModeModal, type PlayTarget } from '@/components/PlayModeModal'
import { Button, Card, SectionTitle, cx } from '@/components/ui'
import { api } from '@/lib/api'
import { formatNumber, plural } from '@/lib/format'
import { decadeOf, EMPTY_FILTERS, GENRE_LABELS, GENRE_STYLE, matchesPopularity } from '@/lib/game'
import type { LaunchOptions } from '@/store/launch'
import { useAllSongs, useLibrary, type Pack } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

const ERAS: Array<{ decade: number; label: string; emoji: string; from: string; to: string }> = [
  { decade: 1960, label: '60-е и раньше', emoji: '🎙️', from: '#78716c', to: '#b45309' },
  { decade: 1970, label: '70-е', emoji: '🕺', from: '#ea580c', to: '#a16207' },
  { decade: 1980, label: '80-е', emoji: '📼', from: '#db2777', to: '#4f46e5' },
  { decade: 1990, label: '90-е', emoji: '💿', from: '#0891b2', to: '#7c3aed' },
  { decade: 2000, label: '2000-е', emoji: '📱', from: '#2563eb', to: '#0f766e' },
  { decade: 2010, label: '2010-е', emoji: '🎧', from: '#9333ea', to: '#e11d48' },
  { decade: 2020, label: '2020-е', emoji: '🚀', from: '#16a34a', to: '#0284c7' }
]

/** Readable message from an IPC error ("Error invoking remote method …: Error: text"). */
function errorText(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  return msg.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

function Tile({
  title,
  subtitle,
  emoji,
  from,
  to,
  onClick,
  delay = 0
}: {
  title: string
  subtitle: string
  emoji: string
  from: string
  to: string
  onClick: () => void
  delay?: number
}) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      whileHover={{ y: -3, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="group relative h-28 overflow-hidden rounded-2xl p-4 text-left text-white shadow-lg cursor-pointer"
      style={{ background: `linear-gradient(135deg, ${from}, ${to})` }}
    >
      <span className="absolute -bottom-3 -right-1 text-6xl opacity-30 transition group-hover:scale-110 group-hover:opacity-50">{emoji}</span>
      <span className="relative block text-base font-bold leading-tight drop-shadow">{title}</span>
      <span className="relative mt-1 block text-xs text-white/80">{subtitle}</span>
      <span className="absolute bottom-3 left-4 flex h-8 w-8 translate-y-2 items-center justify-center rounded-full bg-white/25 opacity-0 backdrop-blur transition group-hover:translate-y-0 group-hover:opacity-100">
        <Play size={14} fill="currentColor" />
      </span>
    </motion.button>
  )
}

function PersonalCard({
  icon,
  title,
  count,
  empty,
  onPlay
}: {
  icon: ReactNode
  title: string
  count: number
  empty: string
  onPlay: () => void
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <span className="bg-gradient-accent flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white shadow-lg shadow-accent/30">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="font-semibold">{title}</div>
        <div className="text-sm text-muted">{count ? `${count} ${plural(count, 'песня', 'песни', 'песен')}` : empty}</div>
      </div>
      <Button variant="secondary" size="sm" onClick={onPlay} disabled={!count}>
        <Play size={14} fill="currentColor" /> Играть
      </Button>
    </Card>
  )
}

export function CollectionsScreen() {
  const songs = useAllSongs()
  const filters = useSettings((s) => s.filters)
  const [target, setTarget] = useState<PlayTarget | null>(null)
  const lib = useLibrary()
  const songStats = useStats((s) => s.songs)
  const popularity = filters.popularity ?? 'all'

  const byGenre = useMemo(() => {
    const counts: Partial<Record<Genre, number>> = {}
    for (const s of songs) if (matchesPopularity(s, popularity)) counts[s.genre] = (counts[s.genre] ?? 0) + 1
    return counts
  }, [songs, popularity])

  const byDecade = useMemo(() => {
    const counts: Record<number, number> = {}
    for (const s of songs) if (s.year && matchesPopularity(s, popularity)) counts[decadeOf(s.year)] = (counts[decadeOf(s.year)] ?? 0) + 1
    return counts
  }, [songs, popularity])

  const favorites = useMemo(() => {
    const ids = new Set(lib.favorites)
    return songs.filter((s) => ids.has(s.id))
  }, [songs, lib.favorites])

  const mistakes = useMemo(() => songs.filter((s) => songStats[s.id]?.lastWon === false), [songs, songStats])

  /** Personal collections ignore the home-screen filters: the player chose these songs. */
  const playPool = (pool: Song[], source: NonNullable<LaunchOptions['source']>, from = '#7c3aed', to = '#db2777') =>
    setTarget({ title: source.label, emoji: source.icon ?? '🎵', from, to, count: pool.length, opts: { pool, filters: EMPTY_FILTERS, source } })

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">Подборки</h1>
          <p className="mt-1 text-muted">Один жанр, одна эпоха, свой плейлист или своя музыка. Нажмите на подборку и выберите, как играть.</p>
        </div>
      </div>

      <SectionTitle hint={popularity === 'all' ? undefined : `известность: ${popularity === 'hits' ? 'только хиты' : popularity === 'popular' ? 'популярное' : 'для знатоков'}`}>
        Жанровые станции
      </SectionTitle>
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3">
        {(Object.keys(GENRE_LABELS) as Genre[]).map((g, i) => {
          const n = byGenre[g] ?? 0
          const st = GENRE_STYLE[g]
          return (
            <Tile
              key={g}
              title={GENRE_LABELS[g]}
              subtitle={`${formatNumber(n)} ${plural(n, 'песня', 'песни', 'песен')}`}
              emoji={st.emoji}
              from={st.from}
              to={st.to}
              delay={i * 0.02}
              onClick={() =>
                setTarget({
                  title: GENRE_LABELS[g],
                  emoji: st.emoji,
                  from: st.from,
                  to: st.to,
                  count: n,
                  opts: { filters: { ...EMPTY_FILTERS, genres: [g], popularity }, source: { label: GENRE_LABELS[g], icon: st.emoji } }
                })
              }
            />
          )
        })}
        <Tile
          title="Случайный жанр"
          subtitle="Пусть решит судьба"
          emoji="🎲"
          from="#475569"
          to="#7c3aed"
          delay={0.36}
          onClick={() => {
            const genres = (Object.keys(GENRE_LABELS) as Genre[]).filter((g) => (byGenre[g] ?? 0) > 0)
            const g = genres[Math.floor(Math.random() * genres.length)]
            const st = GENRE_STYLE[g]
            setTarget({
              title: `🎲 ${GENRE_LABELS[g]}`,
              emoji: st.emoji,
              from: st.from,
              to: st.to,
              count: byGenre[g] ?? 0,
              opts: { filters: { ...EMPTY_FILTERS, genres: [g], popularity }, source: { label: GENRE_LABELS[g], icon: st.emoji } }
            })
          }}
        />
      </div>

      <SectionTitle>Эпохи</SectionTitle>
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {ERAS.map((e, i) => {
          const n = byDecade[e.decade] ?? 0
          return (
            <Tile
              key={e.decade}
              title={e.label}
              subtitle={`${formatNumber(n)} ${plural(n, 'песня', 'песни', 'песен')}`}
              emoji={e.emoji}
              from={e.from}
              to={e.to}
              delay={i * 0.03}
              onClick={() =>
                setTarget({
                  title: `Хиты: ${e.label}`,
                  emoji: e.emoji,
                  from: e.from,
                  to: e.to,
                  count: n,
                  opts: { filters: { ...EMPTY_FILTERS, decades: [e.decade], popularity }, source: { label: `Хиты: ${e.label}`, icon: e.emoji } }
                })
              }
            />
          )
        })}
      </div>

      <SectionTitle>Личное</SectionTitle>
      <div className="mb-8 grid gap-3 md:grid-cols-3">
        <PersonalCard
          icon={<Heart size={20} />}
          title="Избранное"
          count={favorites.length}
          empty="Отмечайте песни сердечком"
          onPlay={() => playPool(favorites, { label: 'Избранное', icon: '❤️' })}
        />
        <PersonalCard
          icon={<RotateCcw size={20} />}
          title="Работа над ошибками"
          count={mistakes.length}
          empty="Пока ни одной ошибки"
          onPlay={() => playPool(mistakes, { label: 'Работа над ошибками', icon: '🔁' })}
        />
        <PersonalCard
          icon={<Music2 size={20} />}
          title="Добавленные песни"
          count={lib.custom.length}
          empty="Добавляются в «Библиотеке»"
          onPlay={() => playPool(lib.custom, { label: 'Мои песни', icon: '🎵' })}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DeezerPacks onPlay={(p) => playPool(p.songs, { label: p.title, icon: '📀' })} />
        <LocalMusic onPlay={(pool) => playPool(pool, { label: 'Своя музыка', icon: '💽' })} />
      </div>
      <PlayModeModal target={target} onClose={() => setTarget(null)} />
    </div>
  )
}

function DeezerPacks({ onPlay }: { onPlay: (pack: Pack) => void }) {
  const { packs, savePack, removePack } = useLibrary()
  const toast = useUi((u) => u.toast)
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState<'link' | 'chart' | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (kind: 'link' | 'chart') => {
    setBusy(kind)
    setError(null)
    try {
      setStage('Загружаем плейлист…')
      const playlist = kind === 'chart' ? await api.fetchChart() : await api.fetchPlaylist(link)
      if (!playlist.tracks.length) throw new Error('В плейлисте нет песен с превью')
      setStage(`Определяем жанры и годы для ${playlist.tracks.length} ${plural(playlist.tracks.length, 'песни', 'песен', 'песен')}…`)
      const classified = await api.classify(playlist.tracks).catch(() => [])
      const pack = savePack(playlist, classified)
      setLink('')
      toast({ title: 'Плейлист добавлен', body: `${pack.title} · ${pack.songs.length} ${plural(pack.songs.length, 'песня', 'песни', 'песен')}`, icon: '📀' })
    } catch (err) {
      setError(errorText(err) || 'Не удалось загрузить плейлист. Проверьте ссылку и подключение к интернету.')
    } finally {
      setBusy(null)
      setStage(null)
    }
  }

  return (
    <Card className="p-6">
      <SectionTitle>Плейлисты Deezer</SectionTitle>
      <p className="mb-4 text-sm text-muted">Вставьте ссылку на любой публичный плейлист Deezer — и играйте только в него. Или возьмите свежий чарт.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (link.trim()) void run('link')
        }}
        className="flex gap-2"
      >
        <div className="flex h-11 flex-1 items-center gap-2 rounded-xl border border-line bg-fg/[0.03] px-3 focus-within:border-accent/60">
          <Link2 size={16} className="text-muted" />
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://www.deezer.com/playlist/…"
            className="h-full flex-1 bg-transparent text-sm outline-none placeholder:text-muted/70"
            spellCheck={false}
          />
        </div>
        <Button variant="primary" type="submit" className="h-11" disabled={!link.trim() || busy !== null}>
          {busy === 'link' ? <Loader2 size={16} className="animate-spin" /> : 'Добавить'}
        </Button>
      </form>
      <Button variant="secondary" className="mt-2 w-full" onClick={() => void run('chart')} disabled={busy !== null}>
        {busy === 'chart' ? <Loader2 size={16} className="animate-spin" /> : <TrendingUp size={16} />} Загрузить чарт Deezer (топ-100)
      </Button>
      {stage && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-accent/10 px-4 py-3 text-sm text-accent">
          <Loader2 size={15} className="animate-spin" /> {stage}
        </div>
      )}
      {error && <div className="mt-3 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>}
      <div className="mt-4 space-y-2">
        {packs.map((p) => (
          <div key={p.id} className="flex items-center gap-3 rounded-xl border border-line p-2.5">
            {p.coverUrl ? (
              <img src={p.coverUrl} alt="" className="h-11 w-11 rounded-lg object-cover" />
            ) : (
              <div className="bg-gradient-accent flex h-11 w-11 items-center justify-center rounded-lg text-white">
                <TrendingUp size={18} />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{p.title}</div>
              <div className="text-xs text-muted">
                {p.songs.length} {plural(p.songs.length, 'песня', 'песни', 'песен')} · {new Date(p.importedAt).toLocaleDateString('ru-RU')}
              </div>
            </div>
            <Button size="sm" variant="secondary" onClick={() => onPlay(p)}>
              <Play size={14} fill="currentColor" />
            </Button>
            <button onClick={() => removePack(p.id)} className="rounded-lg p-2 text-muted hover:bg-bad/10 hover:text-bad cursor-pointer" title="Удалить">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </Card>
  )
}

function LocalMusic({ onPlay }: { onPlay: (pool: Song[]) => void }) {
  const { localFolder, localSongs, setLocal } = useLibrary()
  const toast = useUi((u) => u.toast)
  const [busy, setBusy] = useState(false)

  const scan = async (folder: string) => {
    setBusy(true)
    try {
      const tracks = await api.scanMusicFolder(folder)
      setLocal(folder, tracks)
      toast({ title: 'Музыка найдена', body: `${tracks.length} ${plural(tracks.length, 'файл', 'файла', 'файлов')}`, icon: '💽' })
    } catch (err) {
      toast({ title: 'Не удалось прочитать папку', body: errorText(err), tone: 'error', icon: '⚠️' })
    } finally {
      setBusy(false)
    }
  }

  const pick = async () => {
    const folder = await api.pickMusicFolder()
    if (folder) await scan(folder)
  }

  return (
    <Card className="p-6">
      <SectionTitle>Своя музыка</SectionTitle>
      <p className="mb-4 text-sm text-muted">
        Выберите папку с mp3, m4a, flac или ogg — игра будет загадывать ваши песни, и с режимом «С начала» отрывок звучит с настоящего начала трека.
        Название берётся из имени файла «Исполнитель - Название».
      </p>
      {localFolder ? (
        <div className="rounded-xl border border-line p-3">
          <div className="flex items-center gap-3">
            <span className="bg-gradient-accent flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-white">
              <FolderOpen size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold" title={localFolder}>
                {localFolder}
              </div>
              <div className="text-xs text-muted">
                {localSongs.length} {plural(localSongs.length, 'трек', 'трека', 'треков')}
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" size="sm" onClick={() => onPlay(localSongs)} disabled={!localSongs.length}>
              <Play size={14} fill="currentColor" /> Играть
            </Button>
            <Button variant="secondary" size="sm" onClick={() => void scan(localFolder)} disabled={busy}>
              <RefreshCw size={14} className={cx(busy && 'animate-spin')} /> Обновить
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void pick()} disabled={busy}>
              <FolderOpen size={14} /> Другая папка
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setLocal(null, [])}>
              <Trash2 size={14} /> Забыть
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" className="w-full" onClick={() => void pick()} disabled={busy}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <FolderOpen size={16} />} Выбрать папку с музыкой
        </Button>
      )}
    </Card>
  )
}
