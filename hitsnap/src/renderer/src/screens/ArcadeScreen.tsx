import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, ArrowLeft, ArrowUp, Check, RotateCcw, Trophy, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Song } from '@shared/types'
import { Cover } from '@/components/Cover'
import { PreviewButton } from '@/components/PreviewButton'
import { Button, Card, cx } from '@/components/ui'
import { usePreview } from '@/hooks/usePreview'
import { ACHIEVEMENTS } from '@/lib/achievements'
import { api, isDemo } from '@/lib/api'
import { audio } from '@/lib/audio'
import { createRng } from '@/lib/random'
import { decadeOf, quizOptions, sameArtist } from '@/lib/game'
import { plural } from '@/lib/format'
import { ARCADE_INFO, type ArcadeGame } from '@/lib/quests'
import { shuffle } from '@/lib/random'
import { useAllSongs } from '@/store/library'
import { useSettings } from '@/store/settings'
import { useStats } from '@/store/stats'
import { useUi } from '@/store/ui'

import { BattleGame } from './arcade/battle'
import { BingoGame } from './arcade/bingo'
import { ChainGame } from './arcade/chain'
import { HitsterGame } from './arcade/hitster'
import { CoverGame, MissingGame, OddGame, OlderGame, TimelineGame, WhoseGame } from './arcade/trivia'

// Игротека: quick music trivia without the clip ladder. Every song can be
// listened to before answering («Слушать»).

const STYLE: Record<ArcadeGame, { from: string; to: string }> = {
  older: { from: '#f59e0b', to: '#db2777' },
  timeline: { from: '#0ea5e9', to: '#6366f1' },
  whose: { from: '#8b5cf6', to: '#ec4899' },
  odd: { from: '#16a34a', to: '#0d9488' },
  cover: { from: '#f97316', to: '#be123c' },
  missing: { from: '#0891b2', to: '#4338ca' },
  hitster: { from: '#7c3aed', to: '#0ea5e9' },
  bingo: { from: '#e11d48', to: '#f59e0b' },
  chain: { from: '#0d9488', to: '#65a30d' },
  battle: { from: '#ca8a04', to: '#b91c1c' }
}

/** Songs everyone has a chance with: known year, not too obscure. */
export function ArcadeScreen() {
  const [game, setGame] = useState<ArcadeGame | null>(null)
  const best = useStats((s) => s.arcade)

  if (game) {
    return (
      <div className="mx-auto max-w-3xl">
        <button onClick={() => setGame(null)} className="mb-4 flex items-center gap-1.5 text-sm text-muted hover:text-fg cursor-pointer">
          <ArrowLeft size={16} /> Игротека
        </button>
        <div className="mb-6 flex items-center gap-3">
          <span className="text-4xl">{ARCADE_INFO[game].emoji}</span>
          <div>
            <h1 className="text-2xl font-black tracking-tight">{ARCADE_INFO[game].title}</h1>
            <p className="text-sm text-muted">{ARCADE_INFO[game].subtitle}</p>
          </div>
          {best[game] !== undefined && (
            <div className="ml-auto flex items-center gap-1.5 rounded-full bg-warn/15 px-3 py-1.5 text-sm font-semibold text-warn">
              <Trophy size={15} /> рекорд {best[game]}
            </div>
          )}
        </div>
        {game === 'older' && <OlderGame />}
        {game === 'timeline' && <TimelineGame />}
        {game === 'whose' && <WhoseGame />}
        {game === 'odd' && <OddGame />}
        {game === 'cover' && <CoverGame />}
        {game === 'missing' && <MissingGame />}
        {game === 'hitster' && <HitsterGame />}
        {game === 'bingo' && <BingoGame />}
        {game === 'chain' && <ChainGame />}
        {game === 'battle' && <BattleGame />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-black tracking-tight">Игротека</h1>
      <p className="mb-6 mt-1 text-muted">Мини-игры о музыке: годы, исполнители, обложки, бинго, турниры. Каждая приносит опыт.</p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(Object.keys(ARCADE_INFO) as ArcadeGame[]).map((g, i) => (
          <motion.button
            key={g}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ y: -4, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setGame(g)}
            className="relative h-44 overflow-hidden rounded-3xl p-6 text-left text-white shadow-xl cursor-pointer"
            style={{ background: `linear-gradient(135deg, ${STYLE[g].from}, ${STYLE[g].to})` }}
          >
            <span className="absolute -bottom-4 -right-2 text-8xl opacity-30">{ARCADE_INFO[g].emoji}</span>
            <span className="relative block text-2xl font-black">{ARCADE_INFO[g].title}</span>
            <span className="relative mt-1 block max-w-xs text-sm text-white/85">{ARCADE_INFO[g].subtitle}</span>
            <span className="absolute bottom-5 left-6 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold backdrop-blur">
              {best[g] !== undefined ? `Рекорд: ${best[g]}` : 'Ещё не играли'}
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}
