import { useEffect, useRef } from 'react'
import { audio } from '@/lib/audio'

/** Mirrored spectrum bars; idles as a gentle wave when nothing plays. */
export function Visualizer({ bars = 48, className }: { bars?: number; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const data = new Uint8Array(audio.bins)
    const levels = new Float32Array(bars)
    let frame = 0

    const draw = (t: number) => {
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const styles = getComputedStyle(document.documentElement)
      const grad = ctx.createLinearGradient(0, 0, w, 0)
      grad.addColorStop(0, styles.getPropertyValue('--accent').trim() || '#8b5cf6')
      grad.addColorStop(1, styles.getPropertyValue('--accent-2').trim() || '#ec4899')
      ctx.fillStyle = grad

      const live = audio.spectrum(data)
      const gap = 4
      const bw = Math.max(2, (w - gap * (bars - 1)) / bars)
      for (let i = 0; i < bars; i++) {
        let target: number
        if (live) {
          // Logarithmic-ish bin mapping so the bass does not take all the bars.
          const idx = Math.min(data.length - 1, Math.floor((i / bars) ** 1.6 * data.length * 0.7))
          target = data[idx] / 255
        } else {
          target = 0.08 + 0.05 * Math.sin(t / 600 + i * 0.45)
        }
        levels[i] += (target - levels[i]) * (target > levels[i] ? 0.5 : 0.12)
        const bh = Math.max(3, levels[i] * h * 0.9)
        const x = i * (bw + gap)
        ctx.globalAlpha = live ? 0.95 : 0.45
        ctx.beginPath()
        ctx.roundRect(x, (h - bh) / 2, bw, bh, bw / 2)
        ctx.fill()
      }
      frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [bars])

  return <canvas ref={canvasRef} className={className} />
}
