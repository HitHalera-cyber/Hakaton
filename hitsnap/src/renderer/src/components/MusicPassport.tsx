import { motion } from 'framer-motion'
import { useMemo } from 'react'
import { GENRE_LABELS, GENRE_STYLE } from '@/lib/game'
import { decadeLabel, passportFor } from '@/lib/passport'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'

const MIN_WINS = 5

/** «Музыкальный паспорт»: favourite genre, decade and artists, as a card. */
export function MusicPassport() {
  const songs = useAllSongs()
  const stats = useStats((s) => s.songs)
  const name = useSettings((s) => s.profileName)
  const emoji = useSettings((s) => s.profileEmoji)
  const p = useMemo(() => passportFor(songs, stats), [songs, stats])
  const style = p.genre ? GENRE_STYLE[p.genre] : { from: '#6366f1', to: '#ec4899', emoji: '🎵' }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative mb-8 overflow-hidden rounded-3xl p-6 text-white shadow-xl"
      style={{ background: `linear-gradient(135deg, ${style.from}, ${style.to})` }}
    >
      <span className="absolute -right-4 -top-6 text-[140px] leading-none opacity-20">{style.emoji}</span>
      <div className="relative text-xs font-semibold uppercase tracking-[0.2em] text-white/75">Музыкальный паспорт</div>
      <div className="relative mt-3 flex items-center gap-4">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/20 text-4xl backdrop-blur">{emoji}</div>
        <div className="min-w-0">
          <div className="truncate text-sm text-white/80">{name || 'Ваш профиль'}</div>
          <div className="text-3xl font-black leading-tight">{p.wins >= MIN_WINS ? p.persona : 'Паспорт ещё оформляется'}</div>
        </div>
      </div>
      {p.wins < MIN_WINS ? (
        <div className="relative mt-4 text-sm text-white/85">
          Угадайте ещё {MIN_WINS - p.wins} {MIN_WINS - p.wins === 1 ? 'песню' : MIN_WINS - p.wins < 5 ? 'песни' : 'песен'} — и здесь появятся ваш любимый жанр, эпоха и исполнители.
        </div>
      ) : (
        <div className="relative mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Fact label="Любимый жанр" value={p.genre ? GENRE_LABELS[p.genre] : '—'} />
          <Fact label="Ваша эпоха" value={p.decade ? decadeLabel(p.decade).replace(/-х$/, '-е') : '—'} hint={p.avgYear ? `в среднем ${p.avgYear} год` : undefined} />
          <Fact label="Редкие песни" value={`${Math.round(p.rare * 100)}%`} hint={p.rare >= 0.3 ? 'настоящий знаток' : 'среди угаданных'} />
          <Fact
            label="Любимые артисты"
            value={p.artists[0]?.artist ?? '—'}
            hint={p.artists
              .slice(1)
              .map((a) => a.artist)
              .join(', ')}
          />
        </div>
      )}
    </motion.div>
  )
}

function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl bg-white/15 p-3 backdrop-blur">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-white/70">{label}</div>
      <div className="mt-0.5 truncate text-lg font-bold">{value}</div>
      {hint && <div className="truncate text-xs text-white/75">{hint}</div>}
    </div>
  )
}
