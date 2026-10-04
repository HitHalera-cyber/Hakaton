// Слушатель щипков по одной струне (как в режиме «По струнам»): для «Проверки аппликатуры».
// Щипок ловится по скачку громкости, всплеску верхов или новой ноте в спектре; нота определяется
// по тому, что добавилось в спектре за 0,2 с после щипка.

import { applyGains } from '../core/analysis/calibration';
import { SpectrumAnalyzer } from '../core/analysis/dsp';
import { PluckTracker, pluckFromSpectra, type Pluck } from '../core/analysis/stringPick';
import { store } from '../store';
import { MIC_FRAME, OnsetDetector, attackOf, mic, rmsOf } from './mic';

export interface PluckListenerOptions {
  /** Диапазон нот инструмента. */
  lo: number;
  hi: number;
  onPluck: (p: Pluck) => void;
  onLevel?: (level: number) => void;
}

/** Начать слушать щипки. Возвращает функцию остановки. Бросает ошибку, если нет микрофона. */
export async function listenPlucks(o: PluckListenerOptions): Promise<() => void> {
  await mic.acquire();
  const cal = store.getState().settings.listen.calibration;
  const spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate, (cal?.tuningCents ?? 0) / 100);
  const buf = new Float32Array(MIC_FRAME);
  const loud = new OnsetDetector(0.55);
  const hf = new OnsetDetector(0.6, 0.16);
  const tracker = new PluckTracker();
  let pending: { at: number; pre: Float32Array } | null = null;
  let raf = 0;
  let alive = true;
  const semiNow = () => {
    const g = mic.gain || 1;
    const { semi } = spectrum.semitones(buf, 0);
    for (let i = 0; i < semi.length; i++) semi[i] /= g;
    return applyGains(semi, cal?.gains);
  };
  const tick = () => {
    if (!alive || !mic.read(buf)) return;
    const now = mic.now;
    const rms = rmsOf(buf);
    o.onLevel?.(Math.min(1, rms * 6));
    const quick = loud.feed(rms, now) || hf.feed((attackOf(buf) * 3) / (mic.gain || 1), now);
    const semi = semiNow();
    if (pending && now - pending.at >= 0.2) {
      o.onPluck(pluckFromSpectra(pending.pre, semi, o.lo, o.hi));
      pending = null;
    }
    const hit = tracker.feed(now, semi, quick);
    if (hit) {
      if (pending) o.onPluck(pluckFromSpectra(pending.pre, semi, o.lo, o.hi));
      pending = hit;
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => {
    if (!alive) return;
    alive = false;
    cancelAnimationFrame(raf);
    mic.release();
  };
}
