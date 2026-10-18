import { useState } from 'react'
import type { Song } from '@shared/types'
import { hashString } from '@/lib/random'
import { cx } from './ui'

/** Album art, or a generated gradient tile when there is none (or it fails to load). */
export function Cover({ song, url, className }: { song: Song; url?: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (url && !failed) {
    return <img src={url} alt="" onError={() => setFailed(true)} className={cx('object-cover', className)} draggable={false} />
  }
  const h = hashString(song.id)
  const a = h % 360
  const b = (a + 50 + (h >> 9) % 80) % 360
  return (
    <div
      className={cx('flex items-center justify-center font-black text-white/90 [container-type:size]', className)}
      style={{ background: `linear-gradient(135deg, hsl(${a} 75% 55%), hsl(${b} 70% 40%))` }}
    >
      <span className="text-[45cqmin] leading-none drop-shadow">{song.artist.replace(/^the\s+/i, '').trim()[0]?.toUpperCase()}</span>
    </div>
  )
}
