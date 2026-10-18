// Web Audio playback: sample-accurate clips (1 s really is 1 s), soft fades
// against clicks, an analyser for the visualiser and synthesised UI sounds.

const FADE = 0.012

export interface PlaybackState {
  playing: boolean
  /** Seconds played of the current clip. */
  elapsed: number
  /** Length of the current clip in seconds. */
  length: number
}

class AudioEngine {
  private ctx: AudioContext | null = null
  private master!: GainNode
  private analyser!: AnalyserNode
  private source: AudioBufferSourceNode | null = null
  private clipGain: GainNode | null = null
  private startedAt = 0
  private clipLength = 0
  private volume = 0.8
  private listeners = new Set<() => void>()

  private get context(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext()
      this.master = this.ctx.createGain()
      this.master.gain.value = this.volume
      this.analyser = this.ctx.createAnalyser()
      this.analyser.fftSize = 256
      this.analyser.smoothingTimeConstant = 0.75
      this.master.connect(this.analyser)
      this.analyser.connect(this.ctx.destination)
    }
    return this.ctx
  }

  async decode(data: ArrayBuffer): Promise<AudioBuffer> {
    // decodeAudioData detaches the buffer it is given — keep the caller's copy intact.
    return this.context.decodeAudioData(data.slice(0))
  }

  /** Plays `length` seconds of `buffer` from `offset` (whole remainder when omitted). */
  play(buffer: AudioBuffer, offset: number, length?: number): void {
    const ctx = this.context
    void ctx.resume()
    this.stop(false)
    const len = Math.max(0.05, Math.min(length ?? buffer.duration - offset, buffer.duration - offset))
    const src = ctx.createBufferSource()
    const gain = ctx.createGain()
    src.buffer = buffer
    src.connect(gain).connect(this.master)
    const t = ctx.currentTime + 0.02
    gain.gain.setValueAtTime(0, t)
    gain.gain.linearRampToValueAtTime(1, t + FADE)
    gain.gain.setValueAtTime(1, t + len - FADE)
    gain.gain.linearRampToValueAtTime(0, t + len)
    src.start(t, offset, len)
    src.onended = () => {
      if (this.source === src) {
        this.source = null
        this.emit()
      }
    }
    this.source = src
    this.clipGain = gain
    this.startedAt = t
    this.clipLength = len
    this.emit()
  }

  stop(notify = true): void {
    if (this.source && this.ctx && this.clipGain) {
      const t = this.ctx.currentTime
      this.clipGain.gain.cancelScheduledValues(t)
      this.clipGain.gain.setValueAtTime(this.clipGain.gain.value, t)
      this.clipGain.gain.linearRampToValueAtTime(0, t + FADE)
      try {
        this.source.stop(t + FADE)
      } catch {
        // already stopped
      }
    }
    this.source = null
    if (notify) this.emit()
  }

  state(): PlaybackState {
    if (!this.source || !this.ctx) return { playing: false, elapsed: 0, length: this.clipLength }
    const elapsed = Math.max(0, Math.min(this.clipLength, this.ctx.currentTime - this.startedAt))
    return { playing: true, elapsed, length: this.clipLength }
  }

  setVolume(v: number): void {
    this.volume = v
    if (this.ctx) this.master.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02)
  }

  /** Fills `out` with the current spectrum (0..255); returns false when silent. */
  spectrum(out: Uint8Array<ArrayBuffer>): boolean {
    if (!this.ctx || !this.source) return false
    this.analyser.getByteFrequencyData(out)
    return true
  }

  get bins(): number {
    return 128
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  private emit(): void {
    for (const fn of this.listeners) fn()
  }

  /** Short synthesised cue for right / wrong answers. */
  sfx(kind: 'correct' | 'wrong' | 'tick'): void {
    const ctx = this.context
    void ctx.resume()
    const notes = kind === 'correct' ? [659.25, 783.99, 1046.5] : kind === 'wrong' ? [311.13, 233.08] : [880]
    const step = kind === 'tick' ? 0.05 : 0.09
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const g = ctx.createGain()
      osc.type = kind === 'wrong' ? 'triangle' : 'sine'
      osc.frequency.value = freq
      const t = ctx.currentTime + i * step
      g.gain.setValueAtTime(0, t)
      g.gain.linearRampToValueAtTime(0.18 * this.volume, t + 0.01)
      g.gain.exponentialRampToValueAtTime(0.0001, t + step * 2.2)
      osc.connect(g).connect(ctx.destination)
      osc.start(t)
      osc.stop(t + step * 2.4)
    })
  }
}

export const audio = new AudioEngine()

/** Seconds of near-silence at the start of the buffer (fade-ins, pauses before the intro). */
export function leadingSilence(buffer: AudioBuffer, threshold = 0.02): number {
  const data = buffer.getChannelData(0)
  const limit = Math.min(data.length, buffer.sampleRate * 8)
  const step = Math.max(1, Math.floor(buffer.sampleRate / 200))
  for (let i = 0; i < limit; i += step) {
    if (Math.abs(data[i]) > threshold) return Math.max(0, i / buffer.sampleRate - 0.05)
  }
  return 0
}
