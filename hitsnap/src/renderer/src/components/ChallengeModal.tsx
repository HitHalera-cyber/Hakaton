import { Swords } from 'lucide-react'
import { useMemo, useState } from 'react'
import { CHALLENGE_MODES, decodeChallenge } from '@/lib/challenge'
import { formatNumber } from '@/lib/format'
import { GENRE_LABELS, MODE_INFO, type GameMode } from '@/lib/game'
import { launchChallenge, newChallenge } from '@/store/launch'
import { Modal } from './Modal'
import { MODE_ICONS } from './modeIcons'
import { Button, cx, Segmented } from './ui'

/** «Вызов другу»: start a game a friend can replay by code, or accept their code. */
export function ChallengeModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<'create' | 'accept'>('create')
  const [code, setCode] = useState('')
  const parsed = useMemo(() => (code.trim() ? decodeChallenge(code) : null), [code])

  const create = (mode: GameMode) => {
    onClose()
    launchChallenge(newChallenge(mode))
  }
  const accept = () => {
    if (!parsed) return
    onClose()
    setCode('')
    launchChallenge(parsed)
  }

  return (
    <Modal open={open} onClose={onClose} title="Вызов другу">
      <Segmented<'create' | 'accept'>
        value={tab}
        onChange={setTab}
        options={[
          { value: 'create', label: 'Бросить вызов' },
          { value: 'accept', label: 'Принять вызов' }
        ]}
      />
      {tab === 'create' ? (
        <>
          <p className="mb-4 mt-4 text-sm text-muted">
            Сыграйте сами — в итогах появится код. Отправьте его другу: он услышит те же песни, а в конце увидит, кто набрал больше. Используются ваши фильтры, сложность и
            звуковой эффект.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {CHALLENGE_MODES.map((m) => {
              const Icon = MODE_ICONS[m]
              return (
                <button key={m} onClick={() => create(m)} className="flex items-center gap-3 rounded-2xl border border-line p-3 text-left transition hover:border-accent/50 hover:bg-fg/5 cursor-pointer">
                  <span className="bg-gradient-accent flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white">
                    <Icon size={17} />
                  </span>
                  <span className="text-sm font-semibold">{MODE_INFO[m].title}</span>
                </button>
              )
            })}
          </div>
        </>
      ) : (
        <>
          <p className="mb-3 mt-4 text-sm text-muted">Вставьте код, который прислал друг (начинается с «HS-»).</p>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={3}
            placeholder="HS-…"
            className="w-full resize-none rounded-xl border border-line bg-fg/5 p-3 font-mono text-sm outline-none focus:border-accent"
            spellCheck={false}
          />
          <div className={cx('mt-2 min-h-12 rounded-xl p-3 text-sm', !code.trim() ? 'invisible' : parsed ? 'bg-accent/10' : 'bg-bad/10 text-bad')}>
            {parsed ? (
              <>
                <div className="font-semibold">
                  {parsed.from ? `${parsed.from.name}: ${formatNumber(parsed.from.score)} очков (${parsed.from.correct} из ${parsed.from.total})` : 'Новый вызов'}
                </div>
                <div className="text-muted">
                  {MODE_INFO[parsed.mode].title}
                  {Number.isFinite(parsed.rounds) ? ` · ${parsed.rounds} раундов` : ''}
                  {parsed.filters.genres.length ? ` · ${parsed.filters.genres.map((g) => GENRE_LABELS[g]).join(', ')}` : ''}
                </div>
              </>
            ) : (
              'Код не распознан — проверьте, что он скопирован целиком.'
            )}
          </div>
          <Button variant="primary" size="lg" className="mt-3 w-full" onClick={accept} disabled={!parsed}>
            <Swords size={18} /> Принять вызов
          </Button>
        </>
      )}
    </Modal>
  )
}
