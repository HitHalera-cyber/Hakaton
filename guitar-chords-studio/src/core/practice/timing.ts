// Точность ритма: насколько удар по струнам раньше или позже доли метронома.

/** Ошибка удара (в секундах) относительно ближайшей доли/половины доли. subdivision: 1 — четверти, 2 — восьмые. */
export function beatError(t: number, beats: number[], beatDur: number, subdivision = 1): number | null {
  if (!beats.length) return null;
  const grid: number[] = [];
  for (const b of beats) for (let k = 0; k < subdivision; k++) grid.push(b + (k * beatDur) / subdivision);
  let best = Infinity;
  for (const g of grid) if (Math.abs(t - g) < Math.abs(best)) best = t - g;
  // Дальше половины шага сетки — это не попытка попасть в долю.
  return Math.abs(best) <= beatDur / subdivision / 2 ? best : null;
}

export interface TimingSummary {
  /** Среднее смещение, мс: плюс — отстаёте, минус — спешите. */
  mean: number;
  /** Разброс (стандартное отклонение), мс. */
  spread: number;
  /** Средняя абсолютная ошибка, мс — итоговая «точность». */
  accuracy: number;
  count: number;
}

export function timingSummary(errorsSec: number[]): TimingSummary | null {
  if (!errorsSec.length) return null;
  const ms = errorsSec.map((e) => e * 1000);
  const mean = ms.reduce((a, b) => a + b, 0) / ms.length;
  const spread = Math.sqrt(ms.reduce((a, b) => a + (b - mean) ** 2, 0) / ms.length);
  const accuracy = ms.reduce((a, b) => a + Math.abs(b), 0) / ms.length;
  return { mean: Math.round(mean), spread: Math.round(spread), accuracy: Math.round(accuracy), count: ms.length };
}

export function timingVerdict(s: TimingSummary): string {
  const tendency = Math.abs(s.mean) < 12 ? 'ровно в долю' : s.mean < 0 ? `спешите на ${-s.mean} мс` : `отстаёте на ${s.mean} мс`;
  const level = s.accuracy < 20 ? 'отлично' : s.accuracy < 35 ? 'хорошо' : s.accuracy < 60 ? 'неплохо' : 'нужно потренироваться';
  return `${level}: в среднем ${tendency}, разброс ±${s.spread} мс`;
}
