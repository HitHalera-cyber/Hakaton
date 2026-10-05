// Запись себя: дубли с микрофона (или кабеля), оригинал песни для сравнения и проигрыватель,
// который играет их синхронно — с переключением «оригинал / я / вместе».
// Дубли живут, пока открыта программа (сохранить навсегда — кнопкой «WAV»).

import { audio } from '../core/audio/engine';
import { store } from '../store';
import { metronome } from './metronome';
import { mic } from './mic';

export interface Take {
  id: number;
  name: string;
  samples: Float32Array;
  sampleRate: number;
  /** Момент оригинала (с), на который пришлось начало дубля; null — записан без оригинала. */
  refAt: number | null;
  /** Каким refAt был сразу после записи — от него считается ручной сдвиг. */
  refAt0: number | null;
  /** Во сколько раз поднята громкость при «выравнивании» (1 — как записано). */
  boost: number;
}

export interface Reference {
  name: string;
  buffer: AudioBuffer;
}

export interface RecorderState {
  takes: Take[];
  reference: Reference | null;
  /** Идёт запись: с какого момента (часы звука) и под оригинал ли. */
  recording: { since: number; withRef: boolean } | null;
  /** Что играет: дубль (или null — только оригинал), откуда начали и когда. */
  playing: { takeId: number | null; from: number; at: number } | null;
  /** Баланс: 0 — только оригинал, 1 — только дубль. */
  mix: number;
}

let state: RecorderState = { takes: [], reference: null, recording: null, playing: null, mix: 0.5 };
const listeners = new Set<() => void>();
const set = (patch: Partial<RecorderState>) => {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
};

let nextId = 1;
let refSource: AudioBufferSourceNode | null = null;
let takeSource: AudioBufferSourceNode | null = null;
let refGain: GainNode | null = null;
let takeGain: GainNode | null = null;
let recordRef: { from: number; at: number } | null = null;
let usedMetronome = false;

/** Задержка звука (колонки + микрофон), с: та же, что подстроена в «Ритме». */
function latency() {
  const ms = store.getState().settings.rhythm.latencyMs;
  if (ms != null) return ms / 1000;
  const ctx = audio.context as AudioContext & { outputLatency?: number };
  return (ctx.outputLatency ?? 0) + (ctx.baseLatency ?? 0) + 0.015;
}

/** Длина дорожки сравнения: оригинал или самый длинный кусок. */
export function timelineLength(take: Take | null): number {
  const ref = state.reference?.buffer.duration ?? 0;
  if (!take) return ref;
  const len = take.samples.length / take.sampleRate;
  return Math.max(ref, (take.refAt ?? 0) + len);
}

export const recorder = {
  get state() {
    return state;
  },
  subscribe(l: () => void) {
    listeners.add(l);
    return () => listeners.delete(l);
  },

  async setReference(file: File) {
    const data = await file.arrayBuffer();
    const buffer = await audio.context.decodeAudioData(data);
    this.stop();
    set({ reference: { name: file.name.replace(/\.[^.]+$/, ''), buffer } });
  },
  clearReference() {
    this.stop();
    set({ reference: null });
  },

  /** Начать запись. withRef — играть оригинал с момента from (в наушники!). */
  async record(opts: { withRef: boolean; from?: number; metronome: boolean }) {
    this.stop();
    await mic.acquire();
    const ctx = audio.context;
    await ctx.resume();
    mic.startCapture();
    recordRef = null;
    if (opts.withRef && state.reference) {
      const from = opts.from ?? 0;
      const at = ctx.currentTime + 0.05;
      const src = ctx.createBufferSource();
      src.buffer = state.reference.buffer;
      src.connect(ctx.destination);
      src.start(at, from);
      refSource = src;
      recordRef = { from, at };
    }
    usedMetronome = opts.metronome && !metronome.running;
    if (usedMetronome) metronome.start();
    set({ recording: { since: ctx.currentTime, withRef: recordRef != null }, playing: null });
  },

  /** Остановить запись и сохранить дубль. normalize — поднять громкость до пика 0,9. */
  finishRecording(normalize: boolean): Take | null {
    if (!state.recording) return null;
    const cap = mic.stopCapture();
    mic.release();
    if (usedMetronome) metronome.stop();
    usedMetronome = false;
    refSource?.stop();
    refSource = null;
    set({ recording: null });
    if (!cap || cap.samples.length < cap.sampleRate * 0.3) return null;
    let peak = 0;
    for (const x of cap.samples) peak = Math.max(peak, Math.abs(x));
    const boost = normalize && peak > 1e-4 ? Math.min(30, 0.9 / peak) : 1;
    if (boost !== 1) for (let i = 0; i < cap.samples.length; i++) cap.samples[i] *= boost;
    // Где на оригинале начался дубль: звук гитары доходит до записи с задержкой — вычитаем её.
    const refAt = recordRef ? recordRef.from + (cap.startTime - recordRef.at) - latency() : null;
    const take: Take = {
      id: nextId,
      name: `Дубль ${nextId}`,
      samples: cap.samples,
      sampleRate: cap.sampleRate,
      refAt,
      refAt0: refAt,
      boost,
    };
    nextId++;
    set({ takes: [...state.takes, take] });
    return take;
  },

  remove(id: number) {
    if (state.playing?.takeId === id) this.stop();
    set({ takes: state.takes.filter((t) => t.id !== id) });
  },

  /** Сдвинуть дубль относительно оригинала (подогнать вручную). */
  shift(id: number, refAt: number) {
    set({ takes: state.takes.map((t) => (t.id === id ? { ...t, refAt } : t)) });
  },

  /**
   * Играть с момента from (по оригиналу, если он есть, иначе по дублю): оригинал и дубль вместе,
   * громкость каждого — по балансу mix.
   */
  play(takeId: number | null, from = 0) {
    this.stop();
    const ctx = audio.context;
    void ctx.resume();
    const at = ctx.currentTime + 0.05;
    const take = state.takes.find((t) => t.id === takeId) ?? null;
    const ref = state.reference;
    // Сравнение — только для дубля, записанного под оригинал (или выровненного вручную).
    const withRef = ref && (!take || take.refAt != null);
    if (withRef && ref) {
      refGain = ctx.createGain();
      refGain.connect(ctx.destination);
      const src = ctx.createBufferSource();
      src.buffer = ref.buffer;
      src.connect(refGain);
      if (from < ref.buffer.duration) src.start(at, from);
      refSource = src;
    }
    if (take) {
      const buf = ctx.createBuffer(1, take.samples.length, take.sampleRate);
      buf.copyToChannel(take.samples as Float32Array<ArrayBuffer>, 0);
      takeGain = ctx.createGain();
      takeGain.connect(ctx.destination);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(takeGain);
      const offset = withRef ? (take.refAt ?? 0) : 0;
      const skip = from - offset;
      if (skip < buf.duration) src.start(at + Math.max(0, -skip), Math.max(0, skip));
      takeSource = src;
    }
    this.applyMix(state.mix, take != null && !!withRef);
    const end = () => {
      if (state.playing && state.playing.at === at) set({ playing: null });
    };
    const longest = takeSource && refSource ? null : (takeSource ?? refSource);
    if (longest) longest.onended = end;
    else if (refSource && takeSource) {
      let left = 2;
      refSource.onended = takeSource.onended = () => --left === 0 && end();
    }
    set({ playing: { takeId: take?.id ?? null, from, at } });
  },

  setMix(mix: number) {
    set({ mix });
    this.applyMix(mix, refGain != null && takeGain != null);
  },

  applyMix(mix: number, both: boolean) {
    // Равная громкость при середине: −3 дБ на каждую дорожку.
    const t = audio.context.currentTime;
    if (refGain) refGain.gain.setTargetAtTime(both ? Math.cos((mix * Math.PI) / 2) : 1, t, 0.02);
    if (takeGain) takeGain.gain.setTargetAtTime(both ? Math.sin((mix * Math.PI) / 2) : 1, t, 0.02);
  },

  /** Сколько секунд прошло по дорожке сравнения (null — ничего не играет). */
  position(): number | null {
    const p = state.playing;
    if (!p) return null;
    return p.from + Math.max(0, audio.context.currentTime - p.at);
  },

  stop() {
    for (const s of [refSource, takeSource]) {
      if (!s) continue;
      s.onended = null;
      try {
        s.stop();
      } catch {
        /* ещё не запущен */
      }
    }
    refSource = takeSource = null;
    refGain?.disconnect();
    takeGain?.disconnect();
    refGain = takeGain = null;
    if (state.playing) set({ playing: null });
  },
};
