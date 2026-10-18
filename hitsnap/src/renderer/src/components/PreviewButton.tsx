import { Loader2, Pause, Play } from 'lucide-react'
import type { Song } from '@shared/types'
import type { usePreview } from '@/hooks/usePreview'
import { cx } from './ui'

/** Play/pause for a song's preview outside the game: a round icon, or a pill with «Слушать». */
export function PreviewButton({
  song,
  preview,
  size = 'md',
  label
}: {
  song: Song
  preview: ReturnType<typeof usePreview>
  size?: 'md' | 'lg'
  label?: boolean
}) {
  const playing = preview.current === song.id
  const icon = size === 'lg' || label ? 16 : 15
  const glyph =
    preview.loading === song.id ? (
      <Loader2 size={icon} className="animate-spin" />
    ) : playing ? (
      <Pause size={icon} fill="currentColor" />
    ) : (
      <Play size={icon} fill="currentColor" className={label ? '' : 'ml-0.5'} />
    )
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        void preview.toggle(song)
      }}
      title={playing ? 'Остановить' : 'Послушать превью'}
      className={cx(
        'flex shrink-0 items-center justify-center rounded-full transition cursor-pointer',
        label ? 'h-9 gap-1.5 px-4 text-sm font-semibold' : size === 'lg' ? 'h-11 w-11' : 'h-9 w-9',
        playing ? 'bg-accent text-on-accent shadow-lg shadow-accent/30' : label ? 'bg-accent/12 text-accent hover:bg-accent/20' : 'bg-fg/5 text-muted hover:bg-accent/15 hover:text-accent'
      )}
    >
      {glyph}
      {label && (playing ? 'Стоп' : 'Слушать')}
    </button>
  )
}
