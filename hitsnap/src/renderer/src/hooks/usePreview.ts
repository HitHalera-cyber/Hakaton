import { useEffect, useRef, useState } from 'react'
import type { Song } from '@shared/types'
import { api } from '@/lib/api'
import { audio } from '@/lib/audio'
import { useUi } from '@/store/ui'
import { usePlayback } from './usePlayback'

/** Plays a song's preview from the library, one at a time. */
export function usePreview() {
  const [current, setCurrent] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const playback = usePlayback()

  useEffect(() => {
    if (!playback.playing && current && !loading) setCurrent(null)
  }, [playback.playing, current, loading])

  // Leaving the screen stops a library preview (but never the game's own audio).
  const currentRef = useRef(current)
  currentRef.current = current
  useEffect(() => () => {
    if (currentRef.current) audio.stop()
  }, [])

  const toggle = async (song: Song) => {
    if (current === song.id) {
      audio.stop()
      setCurrent(null)
      return
    }
    setLoading(song.id)
    try {
      const track = await api.resolveTrack(song)
      if (!track) throw new Error('no preview')
      const buffer = await audio.decode(track.audio)
      audio.play(buffer, 0)
      setCurrent(song.id)
    } catch {
      useUi.getState().toast({ title: 'Превью недоступно', body: `${song.artist} — ${song.title}`, tone: 'error', icon: '🔇' })
    } finally {
      setLoading(null)
    }
  }
  const stop = () => {
    if (current) audio.stop()
    setCurrent(null)
  }
  return { current, loading, toggle, stop }
}
