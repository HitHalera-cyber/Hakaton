import { useEffect, useState } from 'react'
import type { Genre, Lang, Song, Tier } from '@shared/types'
import { GENRE_LABELS, LANG_LABELS, YEAR_RANGE } from '@/lib/game'
import { useLibrary } from '@/store/library'
import { Modal } from './Modal'
import { Button, Segmented } from './ui'

const TIERS: Array<{ value: Tier; label: string }> = [
  { value: 1, label: 'Хит' },
  { value: 2, label: 'Популярная' },
  { value: 3, label: 'Редкость' }
]

const field = 'h-10 w-full rounded-xl border border-line bg-fg/[0.03] px-3 text-sm outline-none focus:border-accent/60'

/** Fixes what was detected automatically for a song in «Моя база». */
export function SongEditor({ song, onClose }: { song: Song | null; onClose: () => void }) {
  const update = useLibrary((s) => s.update)
  const [draft, setDraft] = useState<Song | null>(song)
  useEffect(() => setDraft(song), [song])
  const set = (patch: Partial<Song>) => draft && setDraft({ ...draft, ...patch })
  const save = () => {
    if (!draft) return
    update(draft.id, {
      artist: draft.artist.trim() || draft.artist,
      title: draft.title.trim() || draft.title,
      year: draft.year,
      genre: draft.genre,
      tier: draft.tier,
      lang: draft.lang
    })
    onClose()
  }

  return (
    <Modal open={!!song && !!draft} onClose={onClose} title="Песня в базе">
      {draft && (
      <div className="space-y-4">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted">Исполнитель</span>
          <input className={field} value={draft.artist} onChange={(e) => set({ artist: e.target.value })} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted">Название</span>
          <input className={field} value={draft.title} onChange={(e) => set({ title: e.target.value })} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted">Год</span>
            <input
              className={field}
              type="number"
              min={1900}
              max={YEAR_RANGE.max}
              value={draft.year || ''}
              onChange={(e) => set({ year: Number(e.target.value) || 0 })}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted">Жанр</span>
            <select className={`${field} cursor-pointer`} value={draft.genre} onChange={(e) => set({ genre: e.target.value as Genre })}>
              {(Object.keys(GENRE_LABELS) as Genre[]).map((g) => (
                <option key={g} value={g}>
                  {GENRE_LABELS[g]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div>
          <span className="mb-1 block text-xs font-medium text-muted">Известность</span>
          <Segmented<Tier> value={draft.tier} onChange={(tier) => set({ tier })} options={TIERS} />
        </div>
        <div>
          <span className="mb-1 block text-xs font-medium text-muted">Язык</span>
          <Segmented<Lang>
            value={draft.lang}
            onChange={(lang) => set({ lang })}
            options={(Object.keys(LANG_LABELS) as Lang[]).map((l) => ({ value: l, label: LANG_LABELS[l].replace('На ', '').replace('Другие языки', 'другой') }))}
          />
        </div>
      </div>
      )}
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button variant="primary" onClick={save}>
          Сохранить
        </Button>
      </div>
    </Modal>
  )
}
