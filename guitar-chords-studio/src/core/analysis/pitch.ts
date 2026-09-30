// Высота тона с микрофона (алгоритм YIN) — для тюнера.

export interface PitchResult {
  freq: number;
  /** Надёжность 0..1. */
  clarity: number;
}

/** Высота тона по алгоритму YIN. Возвращает null, если в сигнале нет явного тона. */
export function detectPitch(buf: Float32Array, sampleRate: number, minFreq = 30, maxFreq = 1400): PitchResult | null {
  let rms = 0;
  for (let i = 0; i < buf.length; i++) rms += buf[i] * buf[i];
  rms = Math.sqrt(rms / buf.length);
  if (rms < 0.008) return null;

  const maxLag = Math.min(Math.floor(sampleRate / minFreq), Math.floor(buf.length / 2));
  const minLag = Math.max(2, Math.floor(sampleRate / maxFreq));
  const w = buf.length - maxLag;
  const d = new Float32Array(maxLag + 1);
  for (let lag = 1; lag <= maxLag; lag++) {
    let sum = 0;
    for (let i = 0; i < w; i++) {
      const diff = buf[i] - buf[i + lag];
      sum += diff * diff;
    }
    d[lag] = sum;
  }
  // Кумулятивная нормированная разность.
  const cmnd = new Float32Array(maxLag + 1);
  cmnd[0] = 1;
  let running = 0;
  for (let lag = 1; lag <= maxLag; lag++) {
    running += d[lag];
    cmnd[lag] = running > 0 ? (d[lag] * lag) / running : 1;
  }
  const threshold = 0.15;
  let tau = -1;
  for (let lag = minLag; lag <= maxLag; lag++) {
    if (cmnd[lag] < threshold) {
      while (lag + 1 <= maxLag && cmnd[lag + 1] < cmnd[lag]) lag++;
      tau = lag;
      break;
    }
  }
  if (tau < 0) {
    // Порог не достигнут — берём глобальный минимум, если он достаточно глубокий.
    let best = minLag;
    for (let lag = minLag; lag <= maxLag; lag++) if (cmnd[lag] < cmnd[best]) best = lag;
    if (cmnd[best] > 0.35) return null;
    tau = best;
  }
  // Параболическая интерполяция для точности в доли сэмпла.
  let t = tau;
  if (tau > 1 && tau < maxLag) {
    const a = cmnd[tau - 1];
    const b = cmnd[tau];
    const c = cmnd[tau + 1];
    const den = a - 2 * b + c;
    if (den !== 0) t = tau + (0.5 * (a - c)) / den;
  }
  return { freq: sampleRate / t, clarity: Math.max(0, Math.min(1, 1 - cmnd[tau])) };
}

export function freqToMidi(freq: number): number {
  return 69 + 12 * Math.log2(freq / 440);
}
