import { Plus, Trash2, Users } from 'lucide-react'
import { PLAYER_COLORS } from '@/lib/game'
import { useSettings } from '@/store/settings'
import { launch } from '@/store/launch'
import { Modal } from './Modal'
import { Button, Kbd, Segmented } from './ui'

/** Players and rounds for the party mode. */
export function PartySetup({ open, onClose }: { open: boolean; onClose: () => void }) {
  const players = useSettings((s) => s.players)
  const partyRounds = useSettings((s) => s.partyRounds)
  const update = useSettings((s) => s.update)

  const rename = (i: number, name: string) => update({ players: players.map((p, j) => (j === i ? { ...p, name } : p)) })
  const add = () =>
    players.length < 4 &&
    update({ players: [...players, { name: `Игрок ${players.length + 1}`, color: PLAYER_COLORS.find((c) => !players.some((p) => p.color === c)) ?? PLAYER_COLORS[0] }] })
  const remove = (i: number) => players.length > 2 && update({ players: players.filter((_, j) => j !== i) })

  return (
    <Modal open={open} onClose={onClose} title="Вечеринка">
      <p className="mb-5 text-sm text-muted">
        Играет один компьютер на всех. Звучит отрывок — кто узнал, жмёт свою клавишу и ищет песню. Ошибся — отвечают остальные, а отрывок становится длиннее.
      </p>
      <div className="space-y-2">
        {players.map((p, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2">
            <span className="h-4 w-4 shrink-0 rounded-full" style={{ background: p.color }} />
            <input
              value={p.name}
              onChange={(e) => rename(i, e.target.value)}
              maxLength={16}
              className="h-8 flex-1 bg-transparent font-medium outline-none"
              aria-label={`Имя игрока ${i + 1}`}
            />
            <span className="text-xs text-muted">
              клавиша <Kbd>{i + 1}</Kbd>
            </span>
            <button
              onClick={() => remove(i)}
              disabled={players.length <= 2}
              className="rounded-lg p-1.5 text-muted hover:bg-bad/10 hover:text-bad disabled:opacity-30 cursor-pointer"
              aria-label="Убрать игрока"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
      {players.length < 4 && (
        <Button variant="ghost" className="mt-2" onClick={add}>
          <Plus size={16} /> Добавить игрока
        </Button>
      )}
      <div className="mt-5 flex items-center justify-between">
        <span className="text-sm font-medium">Раундов</span>
        <Segmented<number> value={partyRounds} onChange={(n) => update({ partyRounds: n })} options={[5, 10, 15, 20].map((n) => ({ value: n, label: String(n) }))} />
      </div>
      <Button
        variant="primary"
        size="lg"
        className="mt-6 w-full"
        onClick={() => {
          onClose()
          launch('party')
        }}
      >
        <Users size={18} /> Начать вечеринку
      </Button>
    </Modal>
  )
}
