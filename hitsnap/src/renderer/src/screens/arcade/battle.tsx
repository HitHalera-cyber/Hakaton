import { motion } from 'framer-motion'
import { Crown, Heart } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { Button, Chip, Card } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { decadeOf } from '@/lib/game'
import { shuffle } from '@/lib/random'
import { useLibrary } from '@/store/library'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'
import { finish, SongTile, usePool } from './kit'

// «Битва хитов»: an eight-song tournament of the player's taste. Listen to
// both songs, keep the one you like more; the last one standing is your champion.

type Theme = 'all' | 'ru' | 1980 | 1990 | 2000 | 2010 | 2020
const THEMES: Array<{ id: Theme; label: string }> = [
  { id: 'all', label: 'Хиты всех времён' },
  { id: 'ru', label: 'Русские хиты' },
  { id: 1980, label: '80-е' },
  { id: 1990, label: '90-е' },
  { id: 2000, label: '2000-е' },
  { id: 2010, label: '2010-е' },
  { id: 2020, label: '2020-е' }
]
const STAGE_NAMES: Record<number, string> = { 8: 'Четвертьфинал', 4: 'Полуфинал', 2: 'Финал' }

export function BattleGame() {
  const pool = usePool()
  const preview = usePreview()
  const [theme, setTheme] = useState<Theme>('all')
  const candidates = useMemo(
    () => pool.filter((s) => s.tier === 1 && (theme === 'all' ? true : theme === 'ru' ? s.lang === 'ru' : decadeOf(s.year) === theme)),
    [pool, theme]
  )
  const draw = (list: Song[]): Song[] => {
    const seen = new Set<string>()
    return shuffle(list).filter((s) => !seen.has(s.artist) && (seen.add(s.artist), true)).slice(0, 8)
  }
  const [round, setRound] = useState<Song[]>(() => draw(candidates))
  const [winners, setWinners] = useState<Song[]>([])
  const [podium, setPodium] = useState<Song[]>([])
  const [champion, setChampion] = useState<Song | null>(null)
  const favorites = useLibrary((s) => s.favorites)
  const toggleFavorite = useLibrary((s) => s.toggleFavorite)

  const restart = (t: Theme = theme) => {
    preview.stop()
    setTheme(t)
    const list = pool.filter((s) => s.tier === 1 && (t === 'all' ? true : t === 'ru' ? s.lang === 'ru' : decadeOf(s.year) === t))
    setRound(draw(list))
    setWinners([])
    setPodium([])
    setChampion(null)
  }

  const pairIndex = winners.length * 2
  const pair = round.slice(pairIndex, pairIndex + 2)

  const pick = (song: Song) => {
    preview.stop()
    const loser = pair.find((s) => s.id !== song.id)
    const next = [...winners, song]
    if (loser) setPodium((p) => [loser, ...p])
    if (next.length * 2 < round.length) {
      setWinners(next)
      return
    }
    if (next.length === 1) {
      setChampion(song)
      useUi.getState().celebrate()
      finish('battle', (useStats.getState().arcade.battle ?? 0) + 1, 120, false)
      return
    }
    setRound(next)
    setWinners([])
  }

  if (round.length < 2) return <Card className="p-6 text-muted">Для этой темы мало хитов — выберите другую.</Card>

  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        {THEMES.map((t) => (
          <Chip key={String(t.id)} active={theme === t.id} onClick={() => restart(t.id)}>
            {t.label}
          </Chip>
        ))}
      </div>

      {champion ? (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
          <Card className="flex flex-col items-center p-8 text-center">
            <Crown size={36} className="text-warn" />
            <div className="mt-2 text-sm font-semibold uppercase tracking-wider text-muted">Ваш чемпион</div>
            <Cover song={champion} className="mt-4 h-40 w-40 rounded-3xl shadow-2xl" />
            <div className="mt-4 text-2xl font-black">{champion.title}</div>
            <div className="text-muted">
              {champion.artist} · {champion.year}
            </div>
            <div className="mt-5 flex gap-2">
              <Button variant="primary" onClick={() => restart()}>
                Новый турнир
              </Button>
              <Button onClick={() => toggleFavorite(champion.id)}>
                <Heart size={16} fill={favorites.includes(champion.id) ? 'currentColor' : 'none'} /> {favorites.includes(champion.id) ? 'В избранном' : 'В избранное'}
              </Button>
            </div>
            {podium.length > 0 && (
              <div className="mt-6 w-full text-left">
                <div className="mb-2 text-sm font-semibold text-muted">Ваш топ</div>
                {[champion, ...podium].slice(0, 4).map((s, i) => (
                  <div key={s.id} className="flex items-center gap-3 py-1.5">
                    <span className="w-6 text-center font-black text-muted">{i + 1}</span>
                    <Cover song={s} className="h-9 w-9 rounded-lg" />
                    <span className="truncate font-medium">{s.title}</span>
                    <span className="truncate text-sm text-muted">{s.artist}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </motion.div>
      ) : (
        <>
          <div className="mb-3 flex items-center justify-between text-sm">
            <span className="font-semibold">{STAGE_NAMES[round.length] ?? 'Раунд'}</span>
            <span className="text-muted">
              пара {winners.length + 1} из {round.length / 2} · какая песня вам нравится больше?
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {pair.map((s) => (
              <SongTile key={s.id} song={s} preview={preview} onClick={() => pick(s)} showYear />
            ))}
          </div>
        </>
      )}
    </>
  )
}
