import { Loader2, Pause, Play } from 'lucide-react'
import type { Song } from '@shared/types'
import type { usePreview } from '@/hooks/usePreview'
import { cx } from './ui'

/** Round play/pause button for a song's preview outside the game. */
export function PreviewButton({ song, preview, size = 'md' }: { song: Song; preview: ReturnType<typeof usePreview>; size?: 'md' | 'lg' }) {
  const playing = preview.current === song.id
  const icon = size === 'lg' ? 18 : 15
  return (
    <button
      onClick={() => void preview.toggle(song)}
      disabled={preview.disabled}
      title={preview.disabled ? 'Недоступно во время игры' : playing ? 'Остановить' : 'Послушать превью'}
      className={cx(
        'flex shrink-0 items-center justify-center rounded-full transition cursor-pointer disabled:opacity-30 disabled:pointer-events-none',
        size === 'lg' ? 'h-11 w-11' : 'h-9 w-9',
        playing ? 'bg-accent text-on-accent' : 'bg-fg/5 text-muted hover:bg-accent/15 hover:text-accent'
      )}
    >
      {preview.loading === song.id ? (
        <Loader2 size={icon} className="animate-spin" />
      ) : playing ? (
        <Pause size={icon} fill="currentColor" />
      ) : (
        <Play size={icon} fill="currentColor" className="ml-0.5" />
      )}
    </button>
  )
}
