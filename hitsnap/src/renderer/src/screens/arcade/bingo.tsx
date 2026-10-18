import { motion } from 'framer-motion'
import { Ban, Check, Loader2, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Song } from '@shared/types'
import { Button, cx } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { BINGO_SIZE, hasBingo } from '@/lib/arcade'
import { sameArtist } from '@/lib/game'
import { shuffle } from '@/lib/random'
import { useUi } from '@/store/ui'
import { cue, finish, GameOver, usePool } from './kit'

// «Музыкальное бинго»: a 4×4 card of artists. Songs play one after another;
// mark the artist when you hear them. A full row, column or diagonal wins.

const SIZE = BINGO_SIZE
const MAX_SONGS = 30
const SECONDS = 15


type Verdict = 'hit' | 'miss' | 'wrong' | 'pass'

export function BingoGame() {
  const pool = usePool()
  const preview = usePreview()
  const byArtist = useMemo(() => {
    const m = new Map<string, Song[]>()
    for (const s of pool) if (!/[&,]| feat/i.test(s.artist)) m.set(s.artist, [...(m.get(s.artist) ?? []), s])
    return [...m.entries()].filter(([, songs]) => songs.length >= 3)
  }, [pool])

  const deal = useCallback(() => shuffle(byArtist).slice(0, SIZE * SIZE).map(([artist]) => artist), [byArtist])
  const [card, setCard] = useState<string[]>(deal)
  const [marked, setMarked] = useState<boolean[]>(() => Array(SIZE * SIZE).fill(false))
  const [song, setSong] = useState<Song | null>(null)
  const [count, setCount] = useState(0)
  const [verdict, setVerdict] = useState<{ kind: Verdict; cell?: number } | null>(null)
  const [left, setLeft] = useState(SECONDS)
  const [mistakes, setMistakes] = useState(0)
  const [win, setWin] = useState<number[] | null>(null)
  const [over, setOver] = useState(false)
  const used = useRef(new Set<string>())

  /** Next song: often by an artist on the card that is not marked yet, sometimes a decoy. */
  const nextSong = useCallback(
    (cardNow: string[], markedNow: boolean[]): Song => {
      const open = cardNow.filter((_, i) => !markedNow[i])
      const onCard = Math.random() < 0.6 && open.length
      for (let tries = 0; tries < 30; tries++) {
        const artist = onCard ? open[Math.floor(Math.random() * open.length)] : byArtist[Math.floor(Math.random() * byArtist.length)][0]
        if (!onCard && cardNow.includes(artist)) continue
        const songs = byArtist.find(([a]) => a === artist)?.[1] ?? []
        const s = songs.find((x) => !used.current.has(x.id))
        if (s) return s
      }
      return pool[Math.floor(Math.random() * pool.length)]
    },
    [byArtist, pool]
  )

  const advance = useCallback(
    async (cardNow: string[], markedNow: boolean[], n: number) => {
      if (n >= MAX_SONGS) {
        setOver(true)
        finish('bingo', 0, 100, false)
        return
      }
      for (let tries = 0; tries < 5; tries++) {
        const s = nextSong(cardNow, markedNow)
        used.current.add(s.id)
        setSong(s)
        setVerdict(null)
        setLeft(SECONDS)
        if (await preview.play(s, { quiet: true })) break
      }
      setCount(n + 1)
    },
    [nextSong, preview]
  )

  useEffect(() => {
    void advance(card, marked, 0)
    return () => preview.stop()
  }, [])

  const settle = (kind: Verdict, cell?: number) => {
    if (!song || verdict || over) return
    preview.stop()
    const idx = card.findIndex((a) => sameArtist({ ...song, artist: a }, song))
    let nextMarked = marked
    let finalKind = kind
    if (kind === 'hit' && cell !== undefined) {
      if (cell === idx) {
        nextMarked = marked.map((m, i) => m || i === cell)
        setMarked(nextMarked)
        cue('correct')
      } else {
        finalKind = 'wrong'
        setMistakes((m) => m + 1)
        cue('wrong')
      }
    } else if (kind === 'pass') {
      // "Not on my card": right unless the artist is there after all.
      finalKind = idx >= 0 && !marked[idx] ? 'miss' : 'pass'
      if (finalKind === 'miss') cue('wrong')
    }
    setVerdict({ kind: finalKind, cell: finalKind === 'wrong' ? cell : idx >= 0 ? idx : undefined })
    const line = hasBingo(nextMarked)
    setTimeout(() => {
      if (line) {
        setWin(line)
        setOver(true)
        const score = MAX_SONGS + 1 - count
        finish('bingo', score, 150 + score * 20, true)
        useUi.getState().toast({ title: 'БИНГО!', body: `За ${count} песен`, icon: '🎱', tone: 'success' })
        return
      }
      void advance(card, nextMarked, count)
    }, finalKind === 'hit' || finalKind === 'pass' ? 1100 : 2000)
  }

  // Each song has a time limit; when it runs out the song counts as passed.
  useEffect(() => {
    if (!song || verdict || over) return
    if (left <= 0) {
      settle('pass')
      return
    }
    const id = setTimeout(() => setLeft((l) => l - 1), 1000)
    return () => clearTimeout(id)
  }, [left, song, verdict, over])

  const again = () => {
    const c = deal()
    const m = Array(SIZE * SIZE).fill(false)
    used.current.clear()
    setCard(c)
    setMarked(m)
    setMistakes(0)
    setWin(null)
    setOver(false)
    setCount(0)
    void advance(c, m, 0)
  }

  const revealed = !!verdict || over
  const message =
    verdict?.kind === 'hit'
      ? 'Есть! Отмечено.'
      : verdict?.kind === 'wrong'
        ? 'Не тот исполнитель.'
        : verdict?.kind === 'miss'
          ? 'Этот исполнитель был на карточке!'
          : verdict?.kind === 'pass'
            ? 'Верно, его нет на карточке.'
            : null

  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <div className="text-lg font-semibold">Слышите исполнителя с карточки — отмечайте!</div>
        <span className="ml-auto text-sm text-muted">
          песня {Math.min(count, MAX_SONGS)} из {MAX_SONGS} · ошибок {mistakes}
        </span>
      </div>

      <div className="mb-5 flex items-center gap-4 rounded-3xl border border-line bg-surface p-4">
        <div className="bg-gradient-accent flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-white">
          {preview.loading ? <Loader2 size={22} className="animate-spin" /> : <Volume2 size={22} />}
        </div>
        <div className="min-w-0 flex-1">
          {revealed && song ? (
            <>
              <div className="truncate font-bold">
                {song.artist} — {song.title}
              </div>
              <div className={cx('text-sm font-semibold', verdict?.kind === 'hit' || verdict?.kind === 'pass' ? 'text-good' : 'text-bad')}>{message}</div>
            </>
          ) : (
            <>
              <div className="font-bold">Звучит песня №{count}</div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-fg/10">
                <div className="bg-gradient-accent h-full transition-[width] duration-1000 ease-linear" style={{ width: `${(left / SECONDS) * 100}%` }} />
              </div>
            </>
          )}
        </div>
        <Button variant="secondary" onClick={() => settle('pass')} disabled={revealed}>
          <Ban size={16} /> Нет на карточке
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {card.map((artist, i) => {
          const isWin = win?.includes(i)
          const flash = verdict?.cell === i
          return (
            <motion.button
              key={artist}
              whileTap={{ scale: 0.95 }}
              onClick={() => settle('hit', i)}
              disabled={marked[i] || revealed}
              className={cx(
                'relative flex h-24 items-center justify-center rounded-2xl border p-2 text-center text-sm font-bold leading-tight transition cursor-pointer disabled:cursor-default',
                isWin
                  ? 'bg-gradient-accent border-transparent text-white shadow-lg shadow-accent/40'
                  : marked[i]
                    ? 'border-good/60 bg-good/15 text-good'
                    : flash
                      ? verdict?.kind === 'wrong'
                        ? 'border-bad bg-bad/10 text-bad'
                        : 'border-warn bg-warn/15 text-warn'
                      : 'border-line bg-surface hover:border-accent/60 hover:bg-accent/8'
              )}
            >
              {marked[i] && <Check size={16} className="absolute right-2 top-2" />}
              {artist}
            </motion.button>
          )
        })}
      </div>

      {over && (
        <GameOver
          title={win ? `Бинго за ${count} песен! 🎱` : 'Песни кончились'}
          detail={win ? `Ошибок: ${mistakes}. Чем меньше песен понадобилось, тем выше рекорд.` : `Отмечено ${marked.filter(Boolean).length} из ${SIZE * SIZE}. Попробуйте новую карточку.`}
          onAgain={again}
        />
      )}
    </>
  )
}
