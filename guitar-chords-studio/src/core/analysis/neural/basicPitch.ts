// Нейросеть Basic Pitch (Spotify, лицензия Apache-2.0): слушает звук и выдаёт, какие ноты звучат
// в каждый момент (88 нот фортепианного диапазона, ~86 кадров в секунду). Модель обучена на
// настоящих записях — она лучше формул отличает ноту от её обертонов и октав.
// TensorFlow.js подгружается только при выборе этого движка (отдельный файл сборки).

import type { DetectedNote } from '../dsp';

export const BP_RATE = 22050;
/** Длина входа модели: ~2 с. */
export const BP_SAMPLES = 43844;
const HOP = 256;
export const BP_FPS = BP_RATE / HOP;
/** Первая нота выхода — A0. */
export const BP_MIDI_LO = 21;
export const BP_NOTES = 88;
/** Модель «разогревается» по краям окна: звук ставим не с нуля, а после 15 кадров тишины. */
const LEAD_FRAMES = 15;
const LEAD = LEAD_FRAMES * HOP;
/** Сколько звука помещается в одно окно, секунд. */
export const BP_MAX_SECONDS = (BP_SAMPLES - LEAD) / BP_RATE;

export interface ModelFiles {
  json: () => Promise<{
    modelTopology: unknown;
    weightsManifest: { weights: unknown[] }[];
    format?: string;
    generatedBy?: string;
    convertedBy?: string;
    signature?: unknown;
  }>;
  weights: () => Promise<ArrayBuffer>;
}

export interface Activations {
  /** Вероятность каждой ноты по кадрам: [кадр * 88 + нота]. */
  frames: Float32Array;
  onsets: Float32Array;
  nFrames: number;
  /** Кадр, с которого начинается поданный звук. */
  start: number;
}

export interface NeuralModel {
  backend: string;
  run(audio22k: Float32Array): Promise<Activations>;
}

/** Файлы модели рядом с программой (public/models/basic-pitch). */
export const bundledModel = (base = './models/basic-pitch/'): ModelFiles => ({
  json: () => fetch(base + 'model.json').then((r) => r.json()),
  weights: () => fetch(base + 'group1-shard1of1.bin').then((r) => r.arrayBuffer()),
});

/**
 * Загрузить модель. Где считать: видеокарта (WebGL) → WebAssembly (процессор, быстро) → обычный
 * процессор. wasmPath — папка с файлами .wasm.
 */
export async function loadBasicPitch(
  files: ModelFiles,
  backend: 'auto' | 'wasm' | 'cpu' = 'auto',
  wasmPath = './tfjs-wasm/',
): Promise<NeuralModel> {
  const tf = await import('@tensorflow/tfjs-core');
  await import('@tensorflow/tfjs-backend-cpu');
  const converter = await import('@tensorflow/tfjs-converter');
  const tryBackend = async (name: 'webgl' | 'wasm') => {
    try {
      if (name === 'webgl') await import('@tensorflow/tfjs-backend-webgl');
      else {
        const wasm = await import('@tensorflow/tfjs-backend-wasm');
        wasm.setWasmPaths(wasmPath);
      }
      return await tf.setBackend(name);
    } catch (e) {
      console.warn(`[нейросеть] ${name} недоступен:`, e);
      return false;
    }
  };
  let ok = false;
  if (backend === 'auto') ok = await tryBackend('webgl');
  if (!ok && backend !== 'cpu') ok = await tryBackend('wasm');
  if (!ok) await tf.setBackend('cpu');
  await tf.ready();
  const [json, weightData] = await Promise.all([files.json(), files.weights()]);
  const model = await converter.loadGraphModel({
    load: async () => ({
      modelTopology: json.modelTopology as object,
      format: json.format,
      generatedBy: json.generatedBy,
      convertedBy: json.convertedBy,
      signature: json.signature as object,
      weightSpecs: json.weightsManifest.flatMap((g) => g.weights) as never,
      weightData,
    }),
  });
  return {
    backend: tf.getBackend(),
    async run(audio) {
      const input = new Float32Array(BP_SAMPLES);
      input.set(audio.subarray(0, BP_SAMPLES - LEAD), LEAD);
      const x = tf.tensor3d(input, [1, BP_SAMPLES, 1]);
      const out = model.execute(x, ['Identity_1', 'Identity_2']) as import('@tensorflow/tfjs-core').Tensor[];
      const [frames, onsets] = await Promise.all([out[0].data(), out[1].data()]);
      const nFrames = out[0].shape[1] ?? 0;
      tf.dispose([x, ...out]);
      return { frames: Float32Array.from(frames), onsets: Float32Array.from(onsets), nFrames, start: LEAD_FRAMES };
    },
  };
}

/** Пересчёт частоты дискретизации (усреднение по окну — заодно срезает верха перед прореживанием). */
export function resample(x: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return x;
  const ratio = from / to;
  const n = Math.floor(x.length / ratio);
  const out = new Float32Array(n);
  const cum = new Float64Array(x.length + 1);
  for (let i = 0; i < x.length; i++) cum[i + 1] = cum[i] + x[i];
  const half = Math.max(0.5, ratio / 2);
  for (let i = 0; i < n; i++) {
    const c = i * ratio;
    const a = Math.max(0, Math.floor(c - half));
    const b = Math.min(x.length, Math.max(a + 1, Math.ceil(c + half)));
    out[i] = (cum[b] - cum[a]) / (b - a);
  }
  return out;
}

/**
 * Ноты, звучавшие в отрезке [fromSec, toSec) поданного звука: средняя и пиковая вероятность по кадрам.
 * Возвращает ноты сильнее порога, по убыванию силы.
 */
export function notesFromActivations(
  act: Activations,
  fromSec: number,
  toSec: number,
  threshold = 0.3,
  /** Секунда удара по струнам: нота засчитывается, только если тогда же у неё было «начало» (шум и гул начала не имеют). */
  onsetSec?: number,
): DetectedNote[] {
  const f0 = Math.max(0, act.start + Math.floor(fromSec * BP_FPS));
  const f1 = Math.min(act.nFrames, act.start + Math.ceil(toSec * BP_FPS));
  if (f1 <= f0) return [];
  const notes: DetectedNote[] = [];
  for (let k = 0; k < BP_NOTES; k++) {
    let sum = 0;
    let max = 0;
    for (let f = f0; f < f1; f++) {
      const v = act.frames[f * BP_NOTES + k];
      sum += v;
      if (v > max) max = v;
    }
    let strength = 0.5 * (sum / (f1 - f0)) + 0.5 * max;
    if (strength < threshold * 0.5) continue;
    if (onsetSec != null) {
      // «Начало» ноты в момент удара: у заново сыгранной струны оно сильное, у шума и гула — слабое.
      const o = act.start + Math.round(onsetSec * BP_FPS);
      let on = 0;
      // Момент удара известен с точностью ~0,1 с (детектор срабатывает чуть позже) — окно с запасом.
      for (let f = Math.max(0, o - 15); f < Math.min(act.nFrames, o + 20); f++) on = Math.max(on, act.onsets[f * BP_NOTES + k]);
      // Что звучало и до удара без нового «начала» — шум или хвост прошлого аккорда: вычитаем.
      if (on < 0.5 && onsetSec >= 0.4) {
        const r1 = act.start + Math.floor((onsetSec - 0.2) * BP_FPS);
        const r0 = Math.max(act.start, r1 - Math.round(0.4 * BP_FPS));
        let ref = 0;
        for (let f = r0; f < r1; f++) ref = Math.max(ref, act.frames[f * BP_NOTES + k]);
        strength -= ref * 0.6;
      }
      if (strength < threshold) continue;
      if (on < 0.2 && strength < 0.75) continue;
    } else if (strength < threshold) continue;
    notes.push({ midi: BP_MIDI_LO + k, strength });
  }
  return notes.sort((a, b) => b.strength - a.strength);
}
