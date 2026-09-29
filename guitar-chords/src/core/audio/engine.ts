// Звуковой движок: записанные сэмплы гитары (FluidR3 GM, CC BY 3.0) через Web Audio.
//
// Для каждой ноты есть отдельный сэмпл, поэтому звук натуральный на всём грифе. Если сэмпл
// не загрузился — нота синтезируется (запасной вариант, см. pluck.ts). Цепочка эффектов:
// [перегруз + «кабинет» для электрогитары] → реверберация (регулируется) → компрессор → громкость.
// Каждая струна звучит одним голосом: новая нота на той же струне глушит предыдущую, как на гитаре.

import type { Instrument } from '../music/tunings';
import { PLUCK_PRESETS, renderPluck } from './pluck';

export type Timbre = 'steel' | 'nylon' | 'electric' | 'overdrive';
export type PlayMode = 'strum' | 'arpeggio';
export type StrumDirection = 'down' | 'up';

export const TIMBRE_NAMES: Record<Timbre, string> = {
  steel: 'Акустика (стальные струны)',
  nylon: 'Классика (нейлон)',
  electric: 'Электрогитара (чистый звук)',
  overdrive: 'Электрогитара (перегруз)',
};

/** GM-программы для MIDI-экспорта и MIDI-выхода. */
export const TIMBRE_PROGRAM: Record<Timbre | 'bass', number> = { nylon: 24, steel: 25, electric: 27, overdrive: 29, bass: 33 };

type SampleSet = 'steel' | 'nylon' | 'electric' | 'bass';
const SAMPLE_RANGE: Record<SampleSet, [number, number]> = {
  steel: [35, 90],
  nylon: [35, 90],
  electric: [35, 90],
  bass: [23, 67],
};

export interface ChordNote {
  midi: number;
  /** Номер струны — для правила «одна нота на струну». */
  string?: number;
}

export type NoteOutListener = (midi: number, velocity: number, delaySec: number, durationSec: number) => void;

interface Voice {
  src: AudioBufferSourceNode;
  gain: GainNode;
  key: string;
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

function driveCurve(amount: number): Float32Array<ArrayBuffer> {
  const n = 2048;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    curve[i] = Math.tanh(amount * x) / Math.tanh(amount);
  }
  return curve;
}

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private master!: GainNode;
  private input!: GainNode;
  private cleanBus!: GainNode;
  private driveBus!: GainNode;
  private wet!: GainNode;
  private clickBus!: GainNode;
  private buffers = new Map<string, AudioBuffer | null>();
  private loading = new Map<string, Promise<AudioBuffer | null>>();
  private voices = new Set<Voice>();
  private volume = 0.8;
  /** Увеличивается при «Стоп», чтобы отменить ноты, ещё ждущие загрузки сэмпла. */
  private epoch = 0;
  private reverb = 0.25;
  timbre: Timbre = 'steel';
  instrument: Instrument = 'guitar';
  /** Отключить встроенный звук (например, когда играем через внешний MIDI-синтезатор). */
  muted = false;
  onNoteOut: NoteOutListener | null = null;

  get context(): AudioContext {
    return this.ensure();
  }

  get now(): number {
    return this.ensure().currentTime;
  }

  private ensure(): AudioContext {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') void this.ctx.resume();
      return this.ctx;
    }
    const ctx = new AudioContext({ latencyHint: 'interactive' });
    this.ctx = ctx;

    this.input = ctx.createGain();
    this.input.gain.value = 2.2; // сэмплы записаны тихо

    // Чистый путь: лёгкое «присутствие» и срез гула.
    this.cleanBus = ctx.createGain();
    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = 45;
    const presence = ctx.createBiquadFilter();
    presence.type = 'peaking';
    presence.frequency.value = 2800;
    presence.Q.value = 0.8;
    presence.gain.value = 2;

    // Перегруз: усиление → мягкое ограничение → фильтры «гитарного кабинета».
    this.driveBus = ctx.createGain();
    this.driveBus.gain.value = 0;
    const pre = ctx.createGain();
    pre.gain.value = 3;
    const shaper = ctx.createWaveShaper();
    shaper.curve = driveCurve(6);
    shaper.oversample = '4x';
    const cabLow = ctx.createBiquadFilter();
    cabLow.type = 'highpass';
    cabLow.frequency.value = 90;
    const cabMid = ctx.createBiquadFilter();
    cabMid.type = 'peaking';
    cabMid.frequency.value = 900;
    cabMid.Q.value = 0.7;
    cabMid.gain.value = 3;
    const cabHigh = ctx.createBiquadFilter();
    cabHigh.type = 'lowpass';
    cabHigh.frequency.value = 4200;
    cabHigh.Q.value = 0.9;
    const post = ctx.createGain();
    post.gain.value = 0.35;

    const mix = ctx.createGain();
    this.input.connect(this.cleanBus).connect(hp).connect(presence).connect(mix);
    this.input
      .connect(this.driveBus)
      .connect(pre)
      .connect(shaper)
      .connect(cabLow)
      .connect(cabMid)
      .connect(cabHigh)
      .connect(post)
      .connect(mix);

    const conv = ctx.createConvolver();
    conv.buffer = makeImpulseResponse(ctx, 2.2, 3.2);
    this.wet = ctx.createGain();
    this.wet.gain.value = this.reverb * 0.6;

    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -12;
    comp.ratio.value = 3;
    comp.attack.value = 0.004;
    comp.release.value = 0.25;

    this.master = ctx.createGain();
    this.master.gain.value = this.volume;
    this.clickBus = ctx.createGain();
    this.clickBus.gain.value = 0.5;

    // Лимитер в конце — полный аккорд на большой громкости не «хрипит».
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -2;
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.001;
    limiter.release.value = 0.1;

    mix.connect(comp);
    mix.connect(conv).connect(this.wet).connect(comp);
    comp.connect(this.master).connect(limiter).connect(ctx.destination);
    this.clickBus.connect(this.master);
    this.applyTimbre();
    return ctx;
  }

  private sampleSet(): SampleSet {
    if (this.instrument === 'bass') return 'bass';
    if (this.instrument === 'ukulele') return 'nylon';
    return this.timbre === 'overdrive' ? 'electric' : this.timbre;
  }

  private applyTimbre() {
    if (!this.ctx) return;
    const drive = this.timbre === 'overdrive' && this.instrument === 'guitar';
    const t = this.ctx.currentTime;
    this.driveBus.gain.setTargetAtTime(drive ? 1 : 0, t, 0.02);
    this.cleanBus.gain.setTargetAtTime(drive ? 0 : 1, t, 0.02);
  }

  setTimbre(t: Timbre) {
    this.timbre = t;
    this.applyTimbre();
    this.preload();
  }

  setInstrument(i: Instrument) {
    this.instrument = i;
    this.applyTimbre();
    this.preload();
  }

  setVolume(v: number) {
    this.volume = v;
    if (this.ctx) this.master.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02);
  }

  setReverb(v: number) {
    this.reverb = v;
    if (this.ctx) this.wet.gain.setTargetAtTime(v * 0.6, this.ctx.currentTime, 0.05);
  }

  /** Загрузить все сэмплы текущего инструмента заранее, чтобы первый аккорд прозвучал без задержки. */
  preload() {
    const set = this.sampleSet();
    const [lo, hi] = SAMPLE_RANGE[set];
    for (let m = lo; m <= hi; m++) void this.load(set, m);
  }

  private load(set: SampleSet, midi: number): Promise<AudioBuffer | null> {
    const key = `${set}:${midi}`;
    let p = this.loading.get(key);
    if (!p) {
      const ctx = this.ensure();
      p = fetch(`samples/${set}/${midi}.mp3`)
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(r.statusText))))
        .then((data) => ctx.decodeAudioData(data))
        .catch(() => null)
        .then((buf) => {
          this.buffers.set(key, buf);
          return buf;
        });
      this.loading.set(key, p);
    }
    return p;
  }

  /** Буфер ноты и коэффициент скорости (если нота вне диапазона сэмплов — берём ближайший). */
  private async bufferFor(midi: number): Promise<{ buffer: AudioBuffer; rate: number }> {
    const set = this.sampleSet();
    const [lo, hi] = SAMPLE_RANGE[set];
    const src = Math.max(lo, Math.min(hi, midi));
    const buf = await this.load(set, src);
    if (buf) return { buffer: buf, rate: Math.pow(2, (midi - src) / 12) };
    // Запасной синтез.
    const key = `pluck:${this.timbre}:${midi}`;
    let synth = this.buffers.get(key);
    if (!synth) {
      const ctx = this.ensure();
      const preset = PLUCK_PRESETS[this.timbre === 'nylon' ? 'nylon' : this.timbre === 'steel' ? 'acoustic' : 'electric'];
      const data = renderPluck(ctx.sampleRate, midi, preset);
      synth = ctx.createBuffer(1, data.length, ctx.sampleRate);
      synth.copyToChannel(data as Float32Array<ArrayBuffer>, 0);
      this.buffers.set(key, synth);
    }
    return { buffer: synth, rate: 1 };
  }

  /**
   * Сыграть ноту. when — абсолютное время AudioContext (по умолчанию «сейчас»).
   * key — «струна»: новая нота с тем же ключом глушит предыдущую.
   */
  playNote(midi: number, velocity = 0.85, when?: number, key?: string, maxDuration?: number) {
    const ctx = this.ensure();
    const start = Math.max(when ?? ctx.currentTime, ctx.currentTime) + 0.005;
    const vkey = key ?? `n${midi}`;
    this.onNoteOut?.(midi, velocity, start - ctx.currentTime, maxDuration ?? 2.5);
    if (this.muted) return;

    const epoch = this.epoch;
    void this.bufferFor(midi).then(({ buffer, rate }) => {
      if (epoch !== this.epoch) return;
      const t0 = Math.max(start, ctx.currentTime);
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.playbackRate.value = rate;
      const gain = ctx.createGain();
      const v = 0.25 + 0.75 * velocity;
      const length = buffer.duration / rate;
      const end = t0 + Math.min(length, maxDuration ?? length);
      gain.gain.setValueAtTime(v, t0);
      gain.gain.setValueAtTime(v, Math.max(t0, end - 0.35));
      gain.gain.linearRampToValueAtTime(0, end);
      src.connect(gain).connect(this.input);

      // Та же струна — глушим предыдущую ноту в момент новой.
      for (const other of this.voices) {
        if (other.key === vkey) {
          other.gain.gain.cancelScheduledValues(t0);
          other.gain.gain.setTargetAtTime(0, t0, 0.015);
          try {
            other.src.stop(t0 + 0.1);
          } catch {
            // уже остановлен
          }
          this.voices.delete(other);
        }
      }
      const voice: Voice = { src, gain, key: vkey };
      this.voices.add(voice);
      src.onended = () => {
        this.voices.delete(voice);
        gain.disconnect();
      };
      src.start(t0);
      src.stop(end + 0.02);
    });
  }

  /** Бой: вниз — от баса к верхним струнам, вверх — обратно (и чуть тише). */
  strum(
    notes: ChordNote[],
    direction: StrumDirection = 'down',
    when?: number,
    opts: { spread?: number; velocity?: number; duration?: number } = {},
  ) {
    if (!notes.length) return;
    const t = when ?? this.now;
    const sorted = [...notes].sort((a, b) => a.midi - b.midi);
    const ordered = direction === 'down' ? sorted : sorted.reverse();
    const spread = (opts.spread ?? 16) / 1000;
    const vel = opts.velocity ?? (direction === 'down' ? 0.85 : 0.65);
    ordered.forEach((n, i) => {
      const accent = direction === 'down' && i === 0 ? 0.08 : 0;
      this.playNote(
        n.midi,
        Math.min(1, vel + accent - i * 0.02),
        t + i * spread,
        n.string != null ? `s${n.string}` : undefined,
        opts.duration,
      );
    });
  }

  /** Перебор: ноты по очереди от баса. */
  arpeggio(notes: ChordNote[], stepMs = 180, when?: number) {
    const t = when ?? this.now;
    [...notes]
      .sort((a, b) => a.midi - b.midi)
      .forEach((n, i) => this.playNote(n.midi, 0.8, t + (i * stepMs) / 1000, n.string != null ? `s${n.string}` : undefined));
  }

  playChord(notes: ChordNote[], mode: PlayMode, stepMs = 180) {
    if (!notes.length) return;
    this.stopAll(0.03);
    if (mode === 'arpeggio') this.arpeggio(notes, stepMs);
    else this.strum(notes, 'down');
  }

  /** Щелчок метронома. */
  click(when: number, accent: boolean) {
    const ctx = this.ensure();
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = 'square';
    osc.frequency.value = accent ? 1760 : 1175;
    g.gain.setValueAtTime(0, when);
    g.gain.linearRampToValueAtTime(accent ? 0.5 : 0.3, when + 0.001);
    g.gain.exponentialRampToValueAtTime(0.0001, when + 0.05);
    osc.connect(g).connect(this.clickBus);
    osc.start(when);
    osc.stop(when + 0.06);
  }

  /** Быстро заглушить всё, что звучит. */
  stopAll(fade = 0.08) {
    this.epoch++;
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    for (const v of this.voices) {
      v.gain.gain.cancelScheduledValues(t);
      v.gain.gain.setTargetAtTime(0, t, fade / 3);
      try {
        v.src.stop(t + fade + 0.05);
      } catch {
        // источник уже остановлен
      }
    }
    this.voices.clear();
  }
}

export const audio = new AudioEngine();
