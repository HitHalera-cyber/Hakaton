// Разбор песни нейросетью Basic Pitch: она слышит ноты в настоящих записях (перегруз, ревербер,
// пианино, голос) заметно чище, чем поиск пиков в спектре. Её ноты по долям складываются в те же
// признаки, что у формул (хромаграмма и бас), и смешиваются с ними.

import type { SongFeatures } from '../songAnalysis';
import { BP_FPS, BP_MAX_SECONDS, BP_MIDI_LO, BP_NOTES, BP_RATE, resample, type NeuralModel } from './basicPitch';

export interface SongActivations {
  /** Вероятность каждой ноты по кадрам всей песни: [кадр * 88 + нота], BP_FPS кадров в секунду. */
  probs: Float32Array;
  nFrames: number;
}

/** Края окна модель слышит хуже — окна идут внахлёст, края отбрасываются. */
const EDGE = 0.15;

/** Прогнать всю песню (моно, 22 050 Гц) через модель окнами по ~1,8 с. */
export async function songActivations(
  model: NeuralModel,
  audio: Float32Array,
  onProgress?: (p: number) => void,
  cancelled?: () => boolean,
): Promise<SongActivations> {
  const duration = audio.length / BP_RATE;
  const nFrames = Math.ceil(duration * BP_FPS);
  const probs = new Float32Array(nFrames * BP_NOTES);
  const win = BP_MAX_SECONDS;
  const hop = win - 2 * EDGE;
  const total = Math.max(1, Math.ceil(duration / hop));
  for (let k = 0, o = 0; o < duration; k++, o += hop) {
    if (cancelled?.()) break;
    const a = Math.floor(o * BP_RATE);
    const act = await model.run(audio.subarray(a, a + Math.floor(win * BP_RATE)));
    // Берём середину окна (у первого — с начала).
    const keepFrom = k === 0 ? 0 : EDGE;
    const keepTo = win - EDGE;
    for (let f = act.start; f < act.nFrames; f++) {
      const local = (f - act.start) / BP_FPS;
      if (local < keepFrom || local >= keepTo) continue;
      const g = Math.round((o + local) * BP_FPS);
      if (g < 0 || g >= nFrames) continue;
      for (let n = 0; n < BP_NOTES; n++) {
        const v = act.frames[f * BP_NOTES + n];
        const i = g * BP_NOTES + n;
        if (v > probs[i]) probs[i] = v;
      }
    }
    onProgress?.(Math.min(1, (k + 1) / total));
    // Отдаём управление интерфейсу между окнами.
    await new Promise((r) => setTimeout(r, 0));
  }
  return { probs, nFrames };
}

/**
 * Признаки по долям из нот нейросети: хромаграмма — сумма вероятностей нот по названиям;
 * бас — самая низкая уверенно звучащая нота кадра.
 */
export function beatFeaturesFromActivations(
  act: SongActivations,
  beats: number[],
  duration: number,
  /** Во сколько раз звук для нейросети растянут (подстройка строя): секунда песни = timeScale секунд в нём. */
  timeScale = 1,
): { chroma: number[][]; bass: number[][] } {
  const chroma: number[][] = [];
  const bass: number[][] = [];
  const fps = BP_FPS * timeScale;
  for (let b = 0; b < beats.length; b++) {
    const end = b + 1 < beats.length ? beats[b + 1] : duration;
    const f0 = Math.max(0, Math.floor(beats[b] * fps));
    const f1 = Math.min(act.nFrames, Math.max(f0 + 1, Math.ceil(end * fps)));
    const c = new Array(12).fill(0);
    const bs = new Array(12).fill(0);
    for (let f = f0; f < f1; f++) {
      let lowest = -1;
      for (let n = 0; n < BP_NOTES; n++) {
        const v = act.probs[f * BP_NOTES + n];
        if (v < 0.15) continue;
        c[(BP_MIDI_LO + n) % 12] += v;
        if (lowest < 0 && v > 0.35 && BP_MIDI_LO + n <= 57) lowest = n;
      }
      if (lowest >= 0) bs[(BP_MIDI_LO + lowest) % 12] += act.probs[f * BP_NOTES + lowest];
    }
    chroma.push(c);
    bass.push(bs);
  }
  return { chroma, bass };
}

const unit = (v: number[]) => {
  const m = Math.max(...v);
  return m > 0 ? v.map((x) => x / m) : v.map(() => 0);
};

/** Смешать признаки формул и нейросети: w — доля нейросети (0..1). */
export function blendFeatures(f: SongFeatures, n: { chroma: number[][]; bass: number[][] }, w = 0.6): SongFeatures {
  const mix = (a: number[][], b: number[][]) =>
    a.map((row, i) => {
      const x = unit(row);
      const y = unit(b[i] ?? row);
      return x.map((v, p) => (1 - w) * v + w * y[p]);
    });
  return { ...f, chroma: mix(f.chroma, n.chroma), bass: mix(f.bass, n.bass) };
}

/**
 * Звук для нейросети с поправкой на строй записи: песня, записанная на cents выше A = 440,
 * чуть замедляется (и понижается) до точных нот. Возвращает звук 22 050 Гц и timeScale для
 * beatFeaturesFromActivations.
 */
export function tunedForModel(mono: Float32Array, sampleRate: number, cents: number): { audio: Float32Array; timeScale: number } {
  const r = Math.pow(2, -cents / 1200);
  // Считаем, что звук записан с частотой sampleRate·r: при пересчёте в 22 050 Гц высота умножится на r.
  return { audio: resample(mono, sampleRate * r, BP_RATE), timeScale: 1 / r };
}
