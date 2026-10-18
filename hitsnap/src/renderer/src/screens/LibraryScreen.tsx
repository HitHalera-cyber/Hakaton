import { Check, Heart, Loader2, Pause, Play, Plus, Search, Star, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CatalogHit, Genre, Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { Button, Card, Chip, cx, Segmented } from '@/components/ui'
import { usePlayback } from '@/hooks/usePlayback'
import { api } from '@/lib/api'
import { audio } from '@/lib/audio'
import { formatNumber, plural } from '@/lib/format'
import { GENRE_LABELS } from '@/lib/game'
import { search } from '@/lib/search'
import { useGame } from '@/store/game'
import { useAllSongs, useLibrary, useSearchIndex } from '@/store/library'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

type Tab = 'all' | 'fav' | 'mine'
type Filter = 'all' | 'won' | 'missed' | 'new'

/** Plays a song's preview from the library, one at a time. */
function usePreview() {
  const [current, setCurrent] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const playback = usePlayback()
  const inGame = useGame((s) => s.phase === 'playing' || s.phase === 'reveal')

  useEffect(() => {
    if (!playback.playing && current && !loading) setCurrent(null)
  }, [playback.playing, current, loading])

  // Leaving the screen stops a library preview (but never the game's own audio).
  const currentRef = useRef(current)
  currentRef.current = current
  useEffect(() => () => {
    if (currentRef.current) audio.stop()
  }, [])

  const toggle = async (song: Song) => {
    if (current === song.id) {
      audio.stop()
      setCurrent(null)
      return
    }
    setLoading(song.id)
    try {
      const track = await api.resolveTrack(song)
      if (!track) throw new Error('no preview')
      const buffer = await audio.decode(track.audio)
      audio.play(buffer, 0)
      setCurrent(song.id)
    } catch {
      useUi.getState().toast({ title: 'Превью недоступно', body: `${song.artist} — ${song.title}`, tone: 'error', icon: '🔇' })
    } finally {
      setLoading(null)
    }
  }
  return { current, loading, toggle, disabled: inGame }
}

function PreviewButton({ song, preview }: { song: Song; preview: ReturnType<typeof usePreview> }) {
  const playing = preview.current === song.id
  return (
    <button
      onClick={() => void preview.toggle(song)}
      disabled={preview.disabled}
      title={preview.disabled ? 'Недоступно во время игры' : 'Послушать превью'}
      className={cx(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition cursor-pointer disabled:opacity-30 disabled:pointer-events-none',
        playing ? 'bg-accent text-on-accent' : 'bg-fg/5 text-muted hover:bg-accent/15 hover:text-accent'
      )}
    >
      {preview.loading === song.id ? <Loader2 size={15} className="animate-spin" /> : playing ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" className="ml-0.5" />}
    </button>
  )
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
          <p className="mt-1 text-muted">Все песни, которые может загадать игра, и ваши собственные добавления.</p>
        </div>
        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            { value: 'all', label: 'Все песни' },
            { value: 'fav', label: `Избранное${favCount ? ` · ${favCount}` : ''}` },
            { value: 'mine', label: `Мои песни${custom.length ? ` · ${custom.length}` : ''}` }
          ]}
        />
      </div>
      {tab === 'mine' ? <MySongs /> : <AllSongs key={tab} favoritesOnly={tab === 'fav'} />}
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

function AllSongs({ favoritesOnly }: { favoritesOnly?: boolean }) {
  const allSongs = useAllSongs()
  const favorites = useLibrary((s) => s.favorites)
  const songs = useMemo(() => {
    if (!favoritesOnly) return allSongs
    const ids = new Set(favorites)
    return allSongs.filter((s) => ids.has(s.id))
  }, [allSongs, favorites, favoritesOnly])
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
      : [...songs].sort((a, b) => a.artist.localeCompare(b.artist) || a.title.localeCompare(b.title))
    return base.filter((s) => {
      if (genre && s.genre !== genre) return false
      const st = stats[s.id]
      if (filter === 'won') return !!st?.won
      if (filter === 'missed') return !!st && st.won < st.played
      if (filter === 'new') return !st
      return true
    })
  }, [songs, index, query, filter, stats, genre])

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
        <div className="flex gap-2">
          <Chip active={filter === 'all'} onClick={() => setFilter('all')}>Все</Chip>
          <Chip active={filter === 'won'} onClick={() => setFilter('won')}>Угаданные</Chip>
          <Chip active={filter === 'missed'} onClick={() => setFilter('missed')}>С ошибками</Chip>
          <Chip active={filter === 'new'} onClick={() => setFilter('new')}>Ещё не звучали</Chip>
        </div>
      </div>
      <div className="mb-3 text-sm text-muted">
        {formatNumber(list.length)} {plural(list.length, 'песня', 'песни', 'песен')} · прозвучало в игре: {heard} из {songs.length}
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
                  {song.tier === 1 && (
                    <span className="flex shrink-0 items-center gap-0.5 rounded-full bg-warn/15 px-1.5 py-0.5 text-[10px] font-semibold text-warn" title="Мега-хит">
                      <Star size={10} fill="currentColor" /> хит
                    </span>
                  )}
                  {song.tier === 3 && (
                    <span className="shrink-0 rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-semibold text-accent" title="Для знатоков">
                      редкость
                    </span>
                  )}
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
            {favoritesOnly && !songs.length ? 'Отмечайте песни сердечком — после раунда или здесь, в библиотеке.' : 'Ничего не найдено'}
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

function MySongs() {
  const { custom, add, remove } = useLibrary()
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<CatalogHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const preview = usePreview()

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

  const added = new Set(custom.map((s) => s.deezerId))

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <div className="mb-3 text-sm font-semibold">Добавить из каталога Deezer</div>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void find()
          }}
          className="mb-4 flex gap-2"
        >
          <div className="glass flex h-11 flex-1 items-center gap-2 rounded-xl px-3 focus-within:border-accent/60">
            <Search size={18} className="text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Исполнитель или песня"
              className="h-full flex-1 bg-transparent outline-none placeholder:text-muted/70"
            />
          </div>
          <Button variant="primary" type="submit" disabled={busy} className="h-11">
            {busy ? <Loader2 size={16} className="animate-spin" /> : 'Найти'}
          </Button>
        </form>
        {error && <div className="mb-3 rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>}
        {hits && (
          <Card className="divide-y divide-line">
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
                  <Button
                    size="sm"
                    variant={isAdded ? 'ghost' : 'secondary'}
                    disabled={isAdded}
                    onClick={() => {
                      add(h)
                      useUi.getState().toast({ title: 'Песня добавлена', body: `${h.artist} — ${h.title}`, icon: '➕' })
                    }}
                  >
                    {isAdded ? <Check size={14} /> : <Plus size={14} />}
                    {isAdded ? 'Добавлена' : 'Добавить'}
                  </Button>
                </div>
              )
            })}
          </Card>
        )}
        {!hits && (
          <p className="text-sm text-muted">
            Не хватает любимой песни? Найдите её здесь — она попадёт в общий поиск и будет загадываться в играх (кроме «Песни дня»).
          </p>
        )}
      </div>
      <div>
        <div className="mb-3 text-sm font-semibold">Добавленные ({custom.length})</div>
        <Card className="divide-y divide-line">
          {custom.length === 0 && <div className="p-6 text-center text-sm text-muted">Пока пусто</div>}
          {custom.map((song) => (
            <div key={song.id} className="flex items-center gap-3 px-3 py-2.5">
              <PreviewButton song={song} preview={preview} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{song.title}</div>
                <div className="truncate text-xs text-muted">{song.artist}</div>
              </div>
              <button onClick={() => remove(song.id)} className="rounded-lg p-2 text-muted hover:bg-bad/10 hover:text-bad cursor-pointer" title="Удалить">
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </Card>
      </div>
    </div>
  )
}
