import { AnimatePresence, motion } from 'framer-motion'
import { Search, X } from 'lucide-react'
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { Song } from '@shared/types'
import { highlightRanges, search } from '@/lib/search'
import { useSearchIndex } from '@/store/library'
import { cx } from './ui'

function Highlighted({ text, query }: { text: string; query: string }) {
  const ranges = highlightRanges(text, query)
  if (!ranges.length) return <>{text}</>
  const parts: React.ReactNode[] = []
  let pos = 0
  ranges.forEach(([a, b], i) => {
    if (a > pos) parts.push(text.slice(pos, a))
    parts.push(
      <mark key={i} className="rounded bg-accent/20 px-px text-fg">
        {text.slice(a, b)}
      </mark>
    )
    pos = b
  })
  parts.push(text.slice(pos))
  return <>{parts}</>
}

export interface SearchBoxHandle {
  focus: () => void
}

/**
 * Live search over the whole song base. Suggestions update on every keystroke;
 * ↑/↓ choose, Enter submits, Esc clears.
 */
export const SearchBox = forwardRef<
  SearchBoxHandle,
  {
    onPick: (song: Song) => void
    excludeIds?: string[]
    disabled?: boolean
    placeholder?: string
    onEmptyKey?: (e: KeyboardEvent<HTMLInputElement>) => boolean
  }
>(function SearchBox({ onPick, excludeIds = [], disabled, placeholder, onEmptyKey }, ref) {
  const index = useSearchIndex()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useImperativeHandle(ref, () => ({ focus: () => inputRef.current?.focus() }), [])

  const results = useMemo(() => {
    const exclude = new Set(excludeIds)
    return search(index, query, 12).filter((s) => !exclude.has(s.id)).slice(0, 8)
  }, [index, query, excludeIds])

  useEffect(() => setActive(0), [query])

  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const pick = (song: Song) => {
    onPick(song)
    setQuery('')
    setOpen(false)
    inputRef.current?.focus()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!query && onEmptyKey?.(e)) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[active]) pick(results[active])
    } else if (e.key === 'Escape' && query) {
      e.preventDefault()
      e.stopPropagation()
      setQuery('')
    }
  }

  const showList = open && query.trim().length > 0

  return (
    <div className="relative">
      <div
        className={cx(
          'glass flex h-14 items-center gap-3 rounded-2xl px-4 transition',
          showList && 'rounded-b-none',
          'focus-within:border-accent/60 focus-within:shadow-[0_0_0_4px] focus-within:shadow-accent/15'
        )}
      >
        <Search size={20} className="shrink-0 text-muted" />
        <input
          ref={inputRef}
          value={query}
          disabled={disabled}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          placeholder={placeholder ?? 'Начните вводить название или исполнителя…'}
          className="h-full flex-1 bg-transparent text-base outline-none placeholder:text-muted/70"
          spellCheck={false}
          autoComplete="off"
        />
        {query && (
          <button onClick={() => setQuery('')} className="rounded-lg p-1 text-muted hover:bg-fg/5 hover:text-fg cursor-pointer" aria-label="Очистить">
            <X size={16} />
          </button>
        )}
      </div>
      <AnimatePresence>
        {showList && (
          <motion.div
            ref={listRef}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.12 }}
            className="absolute inset-x-0 top-full z-30 max-h-80 overflow-y-auto rounded-b-2xl border border-t-0 border-line bg-surface-2 p-1.5 shadow-2xl backdrop-blur-xl"
          >
            {results.length === 0 ? (
              <div className="px-3 py-4 text-sm text-muted">Ничего не найдено. Попробуйте часть названия или имя исполнителя.</div>
            ) : (
              results.map((song, i) => (
                <button
                  key={song.id}
                  data-idx={i}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(song)}
                  onMouseEnter={() => setActive(i)}
                  className={cx(
                    'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition cursor-pointer',
                    i === active ? 'bg-accent/12' : 'hover:bg-fg/5'
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">
                      <Highlighted text={song.title} query={query} />
                    </span>
                    <span className="block truncate text-sm text-muted">
                      <Highlighted text={song.artist} query={query} />
                    </span>
                  </span>
                  {i === active && <span className="text-xs text-muted">Enter ↵</span>}
                </button>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
})
