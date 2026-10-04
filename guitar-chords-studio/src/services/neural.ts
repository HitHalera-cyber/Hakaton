// Нейросеть для «Слушать аккорд»: загружается один раз при первом выборе движка «Нейросеть».

import {
  BP_MAX_SECONDS,
  BP_RATE,
  bundledModel,
  loadBasicPitch,
  notesFromActivations,
  resample,
  type NeuralModel,
} from '../core/analysis/neural/basicPitch';
import type { DetectedNote } from '../core/analysis/dsp';

let model: Promise<NeuralModel> | null = null;

export const neural = {
  /** Загрузить модель (повторные вызовы ждут ту же загрузку). */
  load(): Promise<NeuralModel> {
    model ??= loadBasicPitch(bundledModel()).catch((e) => {
      model = null;
      throw e;
    });
    return model;
  },

  /**
   * Ноты в звуке: audio — запись с микрофона (sampleRate), onsetSec — где в ней удар по струнам,
   * listenSec — сколько слушать после удара. Ноты ниже lowMidi (ниже басовой струны) отбрасываются.
   */
  async notes(
    audio: Float32Array,
    sampleRate: number,
    onsetSec: number,
    listenSec: number,
    lowMidi: number,
    /** false — звук уже звучал до onsetSec (режим «Держите»): не сравнивать с тем, что было до. */
    fresh = true,
  ): Promise<DetectedNote[]> {
    const m = await this.load();
    // В окно модели (~1,8 с) берём немного до удара (образец шума) и сколько поместится после.
    const before = fresh ? Math.min(onsetSec, 0.6) : 0;
    const from = Math.floor((onsetSec - before) * sampleRate);
    const to = Math.min(audio.length, from + Math.floor(BP_MAX_SECONDS * sampleRate));
    const x = resample(audio.subarray(from, to), sampleRate, BP_RATE);
    const act = await m.run(x);
    return notesFromActivations(
      act,
      before + 0.08,
      Math.min(before + listenSec, (to - from) / sampleRate),
      0.3,
      fresh ? before : undefined,
    ).filter((n) => n.midi >= lowMidi - 1);
  },
};
