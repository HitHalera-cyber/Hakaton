// Синтез гитарной струны (расширенный алгоритм Карплуса — Стронга) на Web Audio.
//
// Для каждой ноты заранее рассчитывается AudioBuffer: шумовой «щипок» проходит через
// линию задержки длиной в период ноты с затухающим сглаживающим фильтром — так получается
// естественное затухание и «деревянный» тембр. Дробная задержка даёт точный строй.
// Затем сигнал проходит через резонансы корпуса, реверберацию и компрессор.
// Внешние сэмплы не нужны — приложение полностью автономно.

import { midiToFreq } from '../music/notes';

export type Timbre = 'acoustic' | 'nylon' | 'electric';
export type PlayMode = 'strum' | 'arpeggio';

export const TIMBRE_NAMES: Record<Timbre, string> = {
  acoustic: 'Акустика (сталь)',
  nylon: 'Классика (нейлон)',
  electric: 'Электрогитара (чистый)',
};

interface TimbreParams {
  /** Время затухания до −60 дБ для ноты A2 (сек). */
  t60: number;
  /** Яркость «щипка» 0..1. */
  brightness: number;
  /** Место щипка от подставки (доля длины струны). */
  pluckPos: number;
  /** Демпфирование высоких частот в петле (0.5 — стандарт, меньше — ярче). */
  damping: number;
}

export const TIMBRES: Record<Timbre, TimbreParams> = {
  acoustic: { t60: 5.5, brightness: 0.8, pluckPos: 0.13, damping: 0.5 },
  nylon: { t60: 4.0, brightness: 0.45, pluckPos: 0.2, damping: 0.5 },
  electric: { t60: 8.0, brightness: 0.95, pluckPos: 0.09, damping: 0.42 },
};

export function renderPluck(sampleRate: number, midi: number, p: TimbreParams): Float32Array {
  const freq = midiToFreq(midi);
  // Высокие ноты затухают быстрее.
  const t60 = Math.max(1.2, p.t60 * Math.pow(110 / freq, 0.45));
  const duration = Math.min(t60 * 0.75 + 0.3, 6);
  const n = Math.floor(sampleRate * duration);
  const out = new Float32Array(n);

  const period = sampleRate / freq;
  // Сглаживающий фильтр петли добавляет задержку `damping` сэмпла.
  const delay = period - p.damping;
  const di = Math.floor(delay);
  const frac = delay - di;
  const rho = Math.pow(0.001, 1 / (freq * t60));

  // Возбуждение: шум, сглаженный однополюсным фильтром (яркость), с «гребёнкой» места щипка.
  const excLen = Math.max(2, Math.round(period));
  const exc = new Float32Array(excLen);
  const a = 0.15 + 0.85 * p.brightness;
  let lp = 0;
  for (let i = 0; i < excLen; i++) {
    lp += a * (Math.random() * 2 - 1 - lp);
    exc[i] = lp;
  }
  const comb = Math.max(1, Math.round(p.pluckPos * period));
  for (let i = excLen - 1; i >= comb; i--) exc[i] -= exc[i - comb];

  const at = (i: number) => (i >= 0 ? out[i] : 0);
  for (let i = 0; i < n; i++) {
    const d0 = (1 - frac) * at(i - di) + frac * at(i - di - 1);
    const d1 = (1 - frac) * at(i - di - 1) + frac * at(i - di - 2);
    const fb = rho * ((1 - p.damping) * d0 + p.damping * d1);
    out[i] = (i < excLen ? exc[i] : 0) + fb;
  }

  // Убираем постоянную составляющую, нормируем громкость, делаем плавный хвост.
  let x1 = 0;
  let y1 = 0;
  let peak = 0;
  for (let i = 0; i < n; i++) {
    const y = out[i] - x1 + 0.995 * y1;
    x1 = out[i];
    y1 = y;
    out[i] = y;
    peak = Math.max(peak, Math.abs(y));
  }
  const gain = peak > 0 ? 0.6 / peak : 0;
  const fade = Math.floor(sampleRate * 0.25);
  for (let i = 0; i < n; i++) {
    const tail = i > n - fade ? (n - i) / fade : 1;
    out[i] *= gain * tail;
  }
  return out;
}

function makeImpulseResponse(ctx: BaseAudioContext, seconds: number, decay: number): AudioBuffer {
  const len = Math.floor(ctx.sampleRate * seconds);
  const ir = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const data = ir.getChannelData(ch);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, decay);
  }
  return ir;
}

interface Voice {
  src: AudioBufferSourceNode;
  gain: GainNode;
}

export class GuitarSynth {
  private ctx: AudioContext | null = null;
  private master!: GainNode;
  private input!: GainNode;
  private buffers = new Map<string, AudioBuffer>();
  private voices = new Set<Voice>();
  private volume = 0.8;
  timbre: Timbre = 'acoustic';

  private ensure(): AudioContext {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') void this.ctx.resume();
      return this.ctx;
    }
    const ctx = new AudioContext({ latencyHint: 'interactive' });
    this.ctx = ctx;

    this.input = ctx.createGain();
    // Резонансы корпуса гитары.
    const body1 = ctx.createBiquadFilter();
    body1.type = 'peaking';
    body1.frequency.value = 105;
    body1.Q.value = 1.4;
    body1.gain.value = 5;
    const body2 = ctx.createBiquadFilter();
    body2.type = 'peaking';
    body2.frequency.value = 230;
    body2.Q.value = 1.2;
    body2.gain.value = 3;
    const air = ctx.createBiquadFilter();
    air.type = 'highshelf';
    air.frequency.value = 3500;
    air.gain.value = -3;

    const reverb = ctx.createConvolver();
    reverb.buffer = makeImpulseResponse(ctx, 1.8, 3);
    const wet = ctx.createGain();
    wet.gain.value = 0.22;
    const dry = ctx.createGain();
    dry.gain.value = 1;

    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14;
    comp.ratio.value = 3;
    comp.attack.value = 0.005;
    comp.release.value = 0.2;

    this.master = ctx.createGain();
    this.master.gain.value = this.volume;

    this.input.connect(body1).connect(body2).connect(air);
    air.connect(dry).connect(comp);
    air.connect(reverb).connect(wet).connect(comp);
    comp.connect(this.master).connect(ctx.destination);
    return ctx;
  }

  private buffer(midi: number): AudioBuffer {
    const ctx = this.ensure();
    const key = `${this.timbre}:${midi}`;
    let buf = this.buffers.get(key);
    if (!buf) {
      const data = renderPluck(ctx.sampleRate, midi, TIMBRES[this.timbre]);
      buf = ctx.createBuffer(1, data.length, ctx.sampleRate);
      buf.copyToChannel(data as Float32Array<ArrayBuffer>, 0);
      this.buffers.set(key, buf);
    }
    return buf;
  }

  setVolume(v: number) {
    this.volume = v;
    if (this.ctx) this.master.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02);
  }

  setTimbre(t: Timbre) {
    this.timbre = t;
  }

  /** Сыграть одну ноту (например, с MIDI-клавиатуры). */
  playNote(midi: number, velocity = 0.9, delay = 0) {
    const ctx = this.ensure();
    const src = ctx.createBufferSource();
    src.buffer = this.buffer(midi);
    const gain = ctx.createGain();
    gain.gain.value = 0.35 + 0.65 * velocity;
    src.connect(gain).connect(this.input);
    const voice: Voice = { src, gain };
    this.voices.add(voice);
    src.onended = () => {
      this.voices.delete(voice);
      gain.disconnect();
    };
    src.start(ctx.currentTime + 0.01 + delay);
  }

  /**
   * Сыграть аккорд.
   * strum — «бой» (почти одновременно, с небольшим разносом от баса к верху),
   * arpeggio — перебор с шагом stepMs.
   */
  playChord(midiNotes: number[], mode: PlayMode, stepMs = 180) {
    if (midiNotes.length === 0) return;
    this.stopAll(0.04);
    const notes = [...midiNotes].sort((a, b) => a - b);
    const step = mode === 'strum' ? 0.018 : stepMs / 1000;
    notes.forEach((m, i) => this.playNote(m, mode === 'strum' ? 0.85 : 0.8, i * step));
  }

  /** Быстро заглушить всё, что звучит. */
  stopAll(fade = 0.08) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    for (const v of this.voices) {
      v.gain.gain.cancelScheduledValues(t);
      v.gain.gain.setValueAtTime(v.gain.gain.value, t);
      v.gain.gain.linearRampToValueAtTime(0, t + fade);
      try {
        v.src.stop(t + fade + 0.01);
      } catch {
        // источник ещё не стартовал или уже остановлен
      }
    }
    this.voices.clear();
  }
}

export const synth = new GuitarSynth();
