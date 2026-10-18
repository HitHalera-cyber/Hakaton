import { AnimatePresence, motion } from 'framer-motion'
import { Bot, Timer, User } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { SearchBox, type SearchBoxHandle } from '@/components/SearchBox'
import { cx } from '@/components/ui'
import { plural } from '@/lib/format'
import { firstLetter, lastLetter } from '@/lib/arcade'
import { useAllSongs, useArtistIndex } from '@/store/library'
import { useUi } from '@/store/ui'
import { cue, finish, GameOver } from './kit'

// «Цепочка артистов»: a word game against the bot. Each artist must begin with
// the last letter of the previous one (rules in lib/arcade).

const TURN_SECONDS = 25
const MISTAKES = 3


/** Solo artists and bands only: duets would make the chain too easy. */
const isSingle = (artist: string): boolean => !/[&,]| feat\.? | x | и /i.test(artist) && /^[\p{L}]/u.test(artist)

interface Link {
  artist: string
  by: 'you' | 'bot'
}

export function ChainGame() {
  const songs = useAllSongs()
  const artistIndex = useArtistIndex()
  const searchRef = useRef<SearchBoxHandle>(null)
  /** Artists the bot knows, the most popular first. */
  const known = useMemo(() => {
    const counts = new Map<string, number>()
    for (const s of songs) if (isSingle(s.artist)) counts.set(s.artist, (counts.get(s.artist) ?? 0) + (4 - s.tier))
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([a]) => a)
  }, [songs])

  const opener = () => known[Math.floor(Math.random() * Math.min(80, known.length))]
  const [chain, setChain] = useState<Link[]>(() => [{ artist: opener(), by: 'bot' }])
  const [left, setLeft] = useState(TURN_SECONDS)
  const [mistakes, setMistakes] = useState(0)
  const [thinking, setThinking] = useState(false)
  const [over, setOver] = useState<'win' | 'lose' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const need = lastLetter(chain[chain.length - 1].artist)
  const used = new Set(chain.map((l) => l.artist.toLowerCase()))
  const moves = chain.filter((l) => l.by === 'you').length

  const end = (result: 'win' | 'lose', moveCount: number) => {
    setOver(result)
    finish('chain', moveCount, moveCount * 40 + (result === 'win' ? 200 : 0), result === 'win')
  }

  // The player's clock runs while it is their turn.
  useEffect(() => {
    if (over || thinking) return
    if (left <= 0) {
      cue('wrong')
      end('lose', moves)
      return
    }
    const id = setTimeout(() => setLeft((l) => l - 1), 1000)
    return () => clearTimeout(id)
  }, [left, over, thinking])

  useEffect(() => {
    if (!over && !thinking) searchRef.current?.focus()
  }, [over, thinking, chain.length])

  const answer = (artist: string) => {
    if (over || thinking) return
    const fail = (msg: string) => {
      cue('wrong')
      setError(msg)
      const m = mistakes + 1
      setMistakes(m)
      if (m >= MISTAKES) end('lose', moves)
    }
    if (firstLetter(artist) !== need) return fail(`«${artist}» не начинается на «${need.toUpperCase()}»`)
    if (used.has(artist.toLowerCase())) return fail(`«${artist}» уже был в цепочке`)
    cue('correct')
    setError(null)
    const withYou: Link[] = [...chain, { artist, by: 'you' }]
    setChain(withYou)
    setThinking(true)
    // The bot answers with a well-known artist on the needed letter, if it can.
    setTimeout(() => {
      const letter = lastLetter(artist)
      const taken = new Set(withYou.map((l) => l.artist.toLowerCase()))
      const options = known.filter((a) => firstLetter(a) === letter && !taken.has(a.toLowerCase())).slice(0, 12)
      setThinking(false)
      if (!options.length) {
        useUi.getState().toast({ title: 'Бот сдался!', body: `Он не знает исполнителей на «${letter.toUpperCase()}»`, icon: '🏳️', tone: 'success' })
        end('win', moves + 1)
        return
      }
      setChain([...withYou, { artist: options[Math.floor(Math.random() * options.length)], by: 'bot' }])
      setLeft(TURN_SECONDS)
    }, 900)
  }

  const again = () => {
    setChain([{ artist: opener(), by: 'bot' }])
    setLeft(TURN_SECONDS)
    setMistakes(0)
    setOver(null)
    setError(null)
    setThinking(false)
  }

  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <div className="text-lg font-semibold">
          Назовите исполнителя на букву{' '}
          <span className="bg-gradient-accent ml-1 inline-flex h-9 w-9 items-center justify-center rounded-xl text-xl font-black uppercase text-white">{need}</span>
        </div>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-muted">ошибок {mistakes}/{MISTAKES}</span>
          <span className={cx('flex items-center gap-1 rounded-full px-3 py-1 font-bold tabular-nums', left <= 5 ? 'bg-bad/15 text-bad' : 'bg-accent/15 text-accent')}>
            <Timer size={14} /> {thinking ? '…' : left}
          </span>
        </div>
      </div>

      {!over && (
        <div className="mb-2">
          <SearchBox
            ref={searchRef}
            index={artistIndex.index}
            onPick={(a) => answer(a.title)}
            disabled={thinking}
            describe={(a) => {
              const n = artistIndex.counts.get(a.title) ?? 0
              return `${n} ${plural(n, 'песня', 'песни', 'песен')} в базе`
            }}
            placeholder={thinking ? 'Бот думает…' : `Исполнитель на «${need.toUpperCase()}»…`}
          />
          <div className={cx('mt-2 h-5 text-sm', error ? 'text-bad' : 'text-muted')}>
            {error ?? 'Буквы ь, ъ, ы, й и конечная y не считаются. Можно отвечать и по-русски, и латиницей.'}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <AnimatePresence initial={false}>
          {chain.map((l, i) => (
            <motion.div
              key={`${l.artist}-${i}`}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className={cx(
                'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-semibold',
                l.by === 'you' ? 'border-accent/50 bg-accent/12' : 'border-line bg-surface'
              )}
            >
              {l.by === 'you' ? <User size={14} className="text-accent" /> : <Bot size={14} className="text-muted" />}
              {l.artist}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {over && (
        <GameOver
          title={over === 'win' ? `Победа! Цепочка из ${chain.length}` : `Ваших ходов: ${moves}`}
          detail={over === 'win' ? 'Бот не нашёл, что ответить.' : left <= 0 ? 'Время вышло.' : 'Три ошибки — игра окончена.'}
          onAgain={again}
        />
      )}
    </>
  )
}
