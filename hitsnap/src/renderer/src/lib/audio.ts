// Web Audio playback: sample-accurate clips (1 s really is 1 s), soft fades
// against clicks, an analyser for the visualiser and synthesised UI sounds.

const FADE = 0.012

/** Ways to mangle a clip for extra challenge (and extra points). */
export type SoundEffect = 'none' | 'reverse' | 'fast' | 'slow' | 'muffled' | 'phone' | 'bass'

export const EFFECTS: Record<SoundEffect, { label: string; hint: string; bonus: number; emoji: string }> = {
  none: { label: 'Без эффекта', hint: 'Песня звучит как есть', bonus: 1, emoji: '🎵' },
  reverse: { label: 'Задом наперёд', hint: 'Отрывок играет в обратную сторону', bonus: 1.6, emoji: '🔄' },
  fast: { label: 'Ускорено', hint: 'Быстрее и выше на треть', bonus: 1.2, emoji: '⏩' },
  slow: { label: 'Замедлено', hint: 'Медленнее и ниже', bonus: 1.2, emoji: '🐢' },
  muffled: { label: 'Из-за стены', hint: 'Как будто играет у соседей', bonus: 1.3, emoji: '🧱' },
  phone: { label: 'По телефону', hint: 'Узкая полоса частот, как в трубке', bonus: 1.25, emoji: '📞' },
  bass: { label: 'Только бас', hint: 'Слышны лишь низкие частоты', bonus: 1.5, emoji: '🔈' }
}

/** A reversed copy of buffer[offset, offset + length). */
function reversedSlice(ctx: BaseAudioContext, buffer: AudioBuffer, offset: number, length: number): AudioBuffer {
  const from = Math.floor(offset * buffer.sampleRate)
  const frames = Math.max(1, Math.min(buffer.length - from, Math.floor(length * buffer.sampleRate)))
  const out = ctx.createBuffer(buffer.numberOfChannels, frames, buffer.sampleRate)
  for (let c = 0; c < buffer.numberOfChannels; c++) {
    const src = buffer.getChannelData(c)
    const dst = out.getChannelData(c)
    for (let i = 0; i < frames; i++) dst[i] = src[from + frames - 1 - i]
  }
  return out
}

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

  /**
   * Plays `length` seconds (of listening time) of `buffer` from `offset` —
   * the whole remainder when omitted — optionally through a sound effect.
   */
  play(buffer: AudioBuffer, offset: number, length?: number, effect: SoundEffect = 'none'): void {
    const ctx = this.context
    void ctx.resume()
    this.stop(false)
    const rate = effect === 'fast' ? 1.35 : effect === 'slow' ? 0.75 : 1
    const available = (buffer.duration - offset) / rate
    const len = Math.max(0.05, Math.min(length ?? available, available))
    const src = ctx.createBufferSource()
    const gain = ctx.createGain()
    let startAt = offset
    if (effect === 'reverse') {
      src.buffer = reversedSlice(ctx, buffer, offset, len)
      startAt = 0
    } else {
      src.buffer = buffer
    }
    src.playbackRate.value = rate
    let chain: AudioNode = src
    const filter = (type: BiquadFilterType, frequency: number, q = 0.7): void => {
      const f = ctx.createBiquadFilter()
      f.type = type
      f.frequency.value = frequency
      f.Q.value = q
      chain.connect(f)
      chain = f
    }
    if (effect === 'muffled') filter('lowpass', 600)
    if (effect === 'bass') filter('lowpass', 180, 1)
    if (effect === 'phone') {
      filter('highpass', 500)
      filter('lowpass', 2800)
    }
    // Filters take loudness away; give some back so effects stay audible.
    const boost = effect === 'bass' ? 2.2 : effect === 'muffled' || effect === 'phone' ? 1.5 : 1
    chain.connect(gain).connect(this.master)
    const t = ctx.currentTime + 0.02
    gain.gain.setValueAtTime(0, t)
    gain.gain.linearRampToValueAtTime(boost, t + FADE)
    gain.gain.setValueAtTime(boost, t + len - FADE)
    gain.gain.linearRampToValueAtTime(0, t + len)
    src.start(t, startAt, len * rate)
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
