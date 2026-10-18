import { useEffect, useState } from 'react'
import { audio, type PlaybackState } from '@/lib/audio'

/** Playback position, refreshed every animation frame while something plays. */
export function usePlayback(): PlaybackState {
  const [state, setState] = useState<PlaybackState>(() => audio.state())
  useEffect(() => {
    let frame = 0
    const tick = () => {
      const s = audio.state()
      setState(s)
      if (s.playing) frame = requestAnimationFrame(tick)
    }
    const unsubscribe = audio.subscribe(() => {
      cancelAnimationFrame(frame)
      tick()
    })
    tick()
    return () => {
      cancelAnimationFrame(frame)
      unsubscribe()
    }
  }, [])
  return state
}
