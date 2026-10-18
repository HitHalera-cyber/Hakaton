import { motion } from 'framer-motion'
import { Check, Download, FileUp, Heart, ListPlus, Loader2, Pencil, Plus, Search, Sparkles, Star, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CatalogHit, Genre, LookupResult, Song } from '@shared/types'
import { PreviewButton } from '@/components/PreviewButton'
import { SongEditor } from '@/components/SongEditor'
import { Button, Card, Chip, cx, Segmented } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { api } from '@/lib/api'
import { formatNumber, plural } from '@/lib/format'
import { GENRE_LABELS, GENRE_STYLE } from '@/lib/game'
import { search } from '@/lib/search'
import { useAllSongs, useLibrary, useSearchIndex } from '@/store/library'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

type Tab = 'all' | 'fav' | 'recent' | 'mine'
type Filter = 'all' | 'won' | 'missed' | 'new'

/** Readable message from an IPC error ("Error invoking remote method …: Error: text"). */
function errorText(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  return msg.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

export function LibraryScreen() {
  const [tab, setTab] = useState<Tab>('all')
  const custom = useLibrary((s) => s.custom)
  const favCount = useLibrary((s) => s.favorites.length)
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">Библиотека</h1>
          <p className="mt-1 text-muted">Все песни, которые может загадать игра, и ваша собственная база.</p>
        </div>
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            { value: 'all', label: 'Все песни' },
            { value: 'fav', label: `Избранное${favCount ? ` · ${favCount}` : ''}` },
            { value: 'recent', label: 'Недавние' },
            { value: 'mine', label: `Моя база${custom.length ? ` · ${custom.length}` : ''}` }
          ]}
        />
      </div>
      {tab === 'mine' ? <MyBase /> : <AllSongs key={tab} source={tab} />}
    </div>
  )
}

function FavToggle({ id }: { id: string }) {
  const fav = useLibrary((s) => s.favorites.includes(id))
  const toggle = useLibrary((s) => s.toggleFavorite)
  return (
    <button
      onClick={() => toggle(id)}
      className={cx('rounded-lg p-1.5 transition cursor-pointer', fav ? 'text-bad' : 'text-muted/40 hover:text-bad')}
      title={fav ? 'Убрать из избранного' : 'В избранное'}
      aria-pressed={fav}
    >
      <Heart size={16} fill={fav ? 'currentColor' : 'none'} />
    </button>
  )
}

function TierBadge({ tier }: { tier: Song['tier'] }) {
  if (tier === 1)
    return (
      <span className="flex shrink-0 items-center gap-0.5 rounded-full bg-warn/15 px-1.5 py-0.5 text-[10px] font-semibold text-warn" title="Мега-хит">
        <Star size={10} fill="currentColor" /> хит
      </span>
    )
  if (tier === 3)
    return (
      <span className="shrink-0 rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-semibold text-accent" title="Для знатоков">
        редкость
      </span>
    )
  return null
}

function AllSongs({ source }: { source: 'all' | 'fav' | 'recent' }) {
  const allSongs = useAllSongs()
  const favorites = useLibrary((s) => s.favorites)
  const recent = useStats((s) => s.recent)
  const songs = useMemo(() => {
    if (source === 'fav') {
      const ids = new Set(favorites)
      return allSongs.filter((s) => ids.has(s.id))
    }
    if (source === 'recent') {
      const byId = new Map(allSongs.map((s) => [s.id, s]))
      return recent.map((id) => byId.get(id)).filter((s): s is Song => !!s)
    }
    return allSongs
  }, [allSongs, favorites, recent, source])
  const index = useSearchIndex()
  const stats = useStats((s) => s.songs)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [genre, setGenre] = useState<Genre | ''>('')
  const [limit, setLimit] = useState(80)
  const preview = usePreview()

  const list = useMemo(() => {
    const inSet = new Set(songs.map((s) => s.id))
    const base = query.trim()
      ? search(index, query, 300).filter((s) => inSet.has(s.id))
      : source === 'recent'
        ? songs
        : [...songs].sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title))
    return base.filter((s) => {
      if (genre && s.genre !== genre) return false
      const st = stats[s.id]
      if (filter === 'won') return !!st?.won
      if (filter === 'missed') return !!st && st.won < st.played
      if (filter === 'new') return !st
      return true
    })
  }, [songs, index, query, filter, stats, genre, source])

  useEffect(() => setLimit(80), [query, filter, genre])

  const heard = Object.keys(stats).length
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="glass flex h-11 min-w-64 flex-1 items-center gap-2 rounded-xl px-3 focus-within:border-accent/60">
          <Search size={18} className="shrink-0 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по названию или исполнителю"
            className="h-full flex-1 bg-transparent outline-none placeholder:text-muted/70"
            spellCheck={false}
          />
        </div>
        <select
          value={genre}
          onChange={(e) => setGenre(e.target.value as Genre | '')}
          className="glass h-11 rounded-xl px-3 text-sm outline-none cursor-pointer"
          aria-label="Жанр"
        >
          <option value="">Все жанры</option>
          {(Object.keys(GENRE_LABELS) as Genre[]).map((g) => (
            <option key={g} value={g}>
              {GENRE_LABELS[g]}
            </option>
          ))}
        </select>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Chip active={filter === 'all'} onClick={() => setFilter('all')}>
          Все
        </Chip>
        <Chip active={filter === 'won'} onClick={() => setFilter('won')}>
          Угаданные
        </Chip>
        <Chip active={filter === 'missed'} onClick={() => setFilter('missed')}>
          С ошибками
        </Chip>
        <Chip active={filter === 'new'} onClick={() => setFilter('new')}>
          Ещё не звучали
        </Chip>
      </div>
      <div className="mb-3 text-sm text-muted">
        {formatNumber(list.length)} {plural(list.length, 'песня', 'песни', 'песен')}
        {source === 'all' && ` · прозвучало в игре: ${formatNumber(heard)} из ${formatNumber(songs.length)}`}
        {source === 'recent' && ' · последние прозвучавшие в игре'}
      </div>
      <Card className="divide-y divide-line">
        {list.slice(0, limit).map((song) => {
          const st = stats[song.id]
          return (
            <div key={song.id} className="flex items-center gap-3 px-4 py-2.5">
              <PreviewButton song={song} preview={preview} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 truncate font-medium">
                  <span className="truncate">{song.title}</span>
                  <TierBadge tier={song.tier} />
                </div>
                <div className="truncate text-sm text-muted">{song.artist}</div>
              </div>
              <span className="hidden w-32 truncate text-right text-xs text-muted md:block">{GENRE_LABELS[song.genre]}</span>
              <span className="w-12 text-right text-sm tabular-nums text-muted">{song.year || ''}</span>
              <span
                className={cx(
                  'w-20 rounded-full px-2 py-0.5 text-center text-xs font-medium',
                  !st ? 'text-muted/60' : st.won ? 'bg-good/15 text-good' : 'bg-bad/10 text-bad'
                )}
                title={st ? `Звучала ${st.played} раз, угадана ${st.won}` : 'Ещё не звучала'}
              >
                {st ? `${st.won}/${st.played}` : '—'}
              </span>
              <FavToggle id={song.id} />
            </div>
          )
        })}
        {list.length === 0 && (
          <div className="p-6 text-center text-sm text-muted">
            {source === 'fav' && !songs.length
              ? 'Отмечайте песни сердечком — после раунда или здесь, в библиотеке.'
              : source === 'recent' && !songs.length
                ? 'Сыграйте пару раундов — здесь появятся прозвучавшие песни.'
                : 'Ничего не найдено'}
          </div>
        )}
      </Card>
      {list.length > limit && (
        <div className="mt-4 text-center">
          <Button onClick={() => setLimit((l) => l + 120)}>Показать ещё</Button>
        </div>
      )}
    </>
  )
}

type AddMode = 'search' | 'list' | 'file'

function MyBase() {
  const { custom, remove } = useLibrary()
  const [mode, setMode] = useState<AddMode>('search')
  const [editing, setEditing] = useState<Song | null>(null)
  const preview = usePreview()

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 font-semibold">
              <Sparkles size={16} className="text-accent" /> Добавить песни в базу
            </div>
            <div className="mt-0.5 text-sm text-muted">Жанр, год, известность и язык определяются автоматически — их можно поправить.</div>
          </div>
          <Segmented<AddMode>
            value={mode}
            onChange={setMode}
            options={[
              { value: 'search', label: 'Поиском' },
              { value: 'list', label: 'Списком' },
              { value: 'file', label: 'Файл' }
            ]}
          />
        </div>
        {mode === 'search' && <AddBySearch />}
        {mode === 'list' && <AddByList />}
        {mode === 'file' && <BackupFile />}
      </Card>

      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Моя база</h2>
          <span className="text-xs text-muted">
            {custom.length} {plural(custom.length, 'песня', 'песни', 'песен')} · участвуют в играх, станциях и поиске
          </span>
        </div>
        <Card className="divide-y divide-line">
          {custom.length === 0 && <div className="p-8 text-center text-sm text-muted">Пока пусто — добавьте песни поиском, списком или из файла.</div>}
          {custom.map((song) => (
            <div key={song.id} className="flex items-center gap-3 px-4 py-2.5">
              <PreviewButton song={song} preview={preview} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 truncate font-medium">
                  <span className="truncate">{song.title}</span>
                  <TierBadge tier={song.tier} />
                </div>
                <div className="truncate text-sm text-muted">{song.artist}</div>
              </div>
              <span
                className="hidden shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white md:inline"
                style={{ background: `linear-gradient(90deg, ${GENRE_STYLE[song.genre].from}, ${GENRE_STYLE[song.genre].to})` }}
              >
                {GENRE_LABELS[song.genre]}
              </span>
              <span className="w-12 text-right text-sm tabular-nums text-muted">{song.year || '—'}</span>
              <button onClick={() => setEditing(song)} className="rounded-lg p-2 text-muted hover:bg-fg/5 hover:text-fg cursor-pointer" title="Изменить">
                <Pencil size={15} />
              </button>
              <button onClick={() => remove(song.id)} className="rounded-lg p-2 text-muted hover:bg-bad/10 hover:text-bad cursor-pointer" title="Удалить">
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </Card>
      </div>
      <SongEditor song={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

function AddBySearch() {
  const { custom, add } = useLibrary()
  const toast = useUi((u) => u.toast)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<CatalogHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const find = async () => {
    if (!query.trim()) return
    setBusy(true)
    setError(null)
    try {
      setHits(await api.searchCatalog(query))
    } catch {
      setError('Каталог недоступен — проверьте подключение к интернету.')
    } finally {
      setBusy(false)
    }
  }

  const addOne = async (hit: CatalogHit) => {
    setAdding(hit.deezerId)
    try {
      const [classified] = await api.classify([hit]).catch(() => [hit])
      const song = add(classified ?? hit)
      toast({ title: 'Песня в базе', body: `${song.artist} — ${song.title} · ${GENRE_LABELS[song.genre]}${song.year ? `, ${song.year}` : ''}`, icon: '➕' })
    } finally {
      setAdding(null)
    }
  }

  const added = new Set(custom.map((s) => s.deezerId))

  return (
    <>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void find()
        }}
        className="flex gap-2"
      >
        <div className="flex h-11 flex-1 items-center gap-2 rounded-xl border border-line bg-fg/[0.03] px-3 focus-within:border-accent/60">
          <Search size={18} className="shrink-0 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Исполнитель или песня — поиск по каталогу Deezer"
            className="h-full flex-1 bg-transparent outline-none placeholder:text-muted/70"
          />
        </div>
        <Button variant="primary" type="submit" disabled={busy} className="h-11">
          {busy ? <Loader2 size={16} className="animate-spin" /> : 'Найти'}
        </Button>
      </form>
      {error && <div className="mt-3 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>}
      {hits && (
        <div className="mt-3 max-h-80 divide-y divide-line overflow-y-auto rounded-xl border border-line">
          {hits.length === 0 && <div className="p-5 text-sm text-muted">Ничего не нашлось</div>}
          {hits.map((h) => {
            const isAdded = added.has(h.deezerId)
            return (
              <div key={h.deezerId} className="flex items-center gap-3 px-3 py-2.5">
                {h.coverUrl ? <img src={h.coverUrl} alt="" className="h-10 w-10 rounded-lg object-cover" /> : <div className="h-10 w-10 rounded-lg bg-fg/10" />}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{h.title}</div>
                  <div className="truncate text-xs text-muted">
                    {h.artist} · {h.album}
                  </div>
                </div>
                <Button size="sm" variant={isAdded ? 'ghost' : 'secondary'} disabled={isAdded || adding !== null} onClick={() => void addOne(h)}>
                  {adding === h.deezerId ? <Loader2 size={14} className="animate-spin" /> : isAdded ? <Check size={14} /> : <Plus size={14} />}
                  {isAdded ? 'В базе' : 'Добавить'}
                </Button>
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}

function AddByList() {
  const addMany = useLibrary((s) => s.addMany)
  const toast = useUi((u) => u.toast)
  const [text, setText] = useState('')
  const [results, setResults] = useState<LookupResult[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const lines = text
    .split('\n')
    .map((l) => l.trim().replace(/^\d+[.)]\s*/, ''))
    .filter(Boolean)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      setResults(await api.lookup(lines))
    } catch (err) {
      setError(errorText(err) || 'Поиск недоступен — проверьте подключение к интернету.')
    } finally {
      setBusy(false)
    }
  }

  const found = (results ?? []).filter((r) => r.hit)

  return (
    <>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        placeholder={'По одной песне в строке:\nQueen - Bohemian Rhapsody\nКино - Группа крови\nDaft Punk - One More Time'}
        className="w-full resize-y rounded-xl border border-line bg-fg/[0.03] p-3 text-sm outline-none placeholder:text-muted/60 focus:border-accent/60"
        spellCheck={false}
      />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => void run()} disabled={!lines.length || busy}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <ListPlus size={16} />}
          {busy ? `Ищем ${lines.length} ${plural(lines.length, 'песню', 'песни', 'песен')}…` : 'Найти и определить жанры'}
        </Button>
        <span className="text-xs text-muted">До 200 строк за раз. Формат: «Исполнитель - Название».</span>
      </div>
      {error && <div className="mt-3 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>}
      {results && (
        <div className="mt-4">
          <div className="max-h-80 divide-y divide-line overflow-y-auto rounded-xl border border-line">
            {results.map((r, i) => (
              <motion.div
                key={`${r.query}-${i}`}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: Math.min(i, 20) * 0.02 }}
                className="flex items-center gap-3 px-3 py-2"
              >
                {r.hit ? <Check size={16} className="shrink-0 text-good" /> : <X size={16} className="shrink-0 text-bad" />}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{r.hit ? `${r.hit.artist} — ${r.hit.title}` : r.query}</div>
                  {!r.hit && <div className="text-xs text-bad">не найдено или нет превью</div>}
                </div>
                {r.hit && (
                  <span className="shrink-0 text-xs text-muted">
                    {GENRE_LABELS[r.hit.meta.genre]}
                    {r.hit.meta.year ? ` · ${r.hit.meta.year}` : ''}
                  </span>
                )}
              </motion.div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-sm text-muted">
              Найдено {found.length} из {results.length}
            </span>
            <Button
              variant="primary"
              disabled={!found.length}
              onClick={() => {
                const n = addMany(found.map((r) => r.hit!))
                toast({ title: 'База пополнена', body: `${n} ${plural(n, 'новая песня', 'новые песни', 'новых песен')}`, icon: '📚' })
                setResults(null)
                setText('')
              }}
            >
              <Plus size={16} /> Добавить найденные ({found.length})
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

function BackupFile() {
  const { exportData, importData } = useLibrary()
  const toast = useUi((u) => u.toast)
  const fileRef = useRef<HTMLInputElement>(null)

  const download = () => {
    const blob = new Blob([JSON.stringify(exportData(), null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `hitsnap-база-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const upload = async (file: File) => {
    try {
      const res = importData(JSON.parse(await file.text()))
      toast({
        title: 'Импорт завершён',
        body: `Песен: ${res.songs}, плейлистов: ${res.packs}, избранных: ${res.favorites}`,
        icon: '📥',
        tone: 'success'
      })
    } catch (err) {
      toast({ title: 'Не удалось импортировать', body: errorText(err), icon: '⚠️', tone: 'error' })
    }
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <button onClick={download} className="glass flex items-center gap-4 rounded-2xl p-4 text-left transition hover:border-accent/50 cursor-pointer">
        <span className="bg-gradient-accent flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white">
          <Download size={20} />
        </span>
        <span>
          <span className="block font-semibold">Сохранить в файл</span>
          <span className="block text-sm text-muted">Моя база, плейлисты и избранное — для резервной копии или другого компьютера</span>
        </span>
      </button>
      <button onClick={() => fileRef.current?.click()} className="glass flex items-center gap-4 rounded-2xl p-4 text-left transition hover:border-accent/50 cursor-pointer">
        <span className="bg-gradient-accent flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white">
          <FileUp size={20} />
        </span>
        <span>
          <span className="block font-semibold">Загрузить из файла</span>
          <span className="block text-sm text-muted">Добавит песни из сохранённой базы, ничего не удаляя</span>
        </span>
      </button>
      <input
        ref={fileRef}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void upload(f)
          e.target.value = ''
        }}
      />
    </div>
  )
}
