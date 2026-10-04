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

export type HitZone = 'ok' | 'near' | 'off';

/** Пороги оценки удара, мс: до OK — «в долю», до NEAR — «чуть», дальше — промах. */
export const HIT_OK_MS = 30;
export const HIT_NEAR_MS = 70;

/** Оценка одного удара словами — то, что видно крупно сразу после удара. */
export function classifyHit(errSec: number): { zone: HitZone; text: string } {
  const ms = Math.round(errSec * 1000);
  const a = Math.abs(ms);
  if (a <= HIT_OK_MS) return { zone: 'ok', text: 'В долю ✓' };
  const side = ms < 0 ? 'рано' : 'поздно';
  if (a <= HIT_NEAR_MS) return { zone: 'near', text: `Чуть ${side} (${ms > 0 ? '+' : '−'}${a} мс)` };
  return { zone: 'off', text: `${side[0].toUpperCase()}${side.slice(1)}! (${ms > 0 ? '+' : '−'}${a} мс)` };
}

/** Сколько последних ударов подряд попали в долю. */
export function hitStreak(errorsSec: number[]): number {
  let n = 0;
  for (let i = errorsSec.length - 1; i >= 0 && Math.abs(errorsSec[i] * 1000) <= HIT_OK_MS; i--) n++;
  return n;
}

/** Общий итог простыми словами и совет. */
export function timingAdvice(s: TimingSummary): { zone: HitZone; title: string; tip: string } {
  const zone: HitZone = s.accuracy <= HIT_OK_MS ? 'ok' : s.accuracy <= HIT_NEAR_MS ? 'near' : 'off';
  const title = zone === 'ok' ? 'Вы держите ритм ровно' : zone === 'near' ? 'Ритм почти ровный' : 'Ритм пока плавает';
  const tip =
    Math.abs(s.mean) >= 15
      ? s.mean < 0
        ? 'Вы чаще спешите — дождитесь щелчка, бейте чуть позже.'
        : 'Вы чаще отстаёте — бейте чуть раньше, вместе со щелчком.'
      : s.spread > HIT_NEAR_MS
        ? 'В среднем в долю, но удары скачут — снизьте темп и считайте вслух «раз-и-два-и».'
        : zone === 'ok'
          ? 'Отлично! Попробуйте темп побыстрее.'
          : 'Держите руку в постоянном движении, как маятник.';
  return { zone, title, tip };
}

/**
 * Где в буфере начался удар (индекс отсчёта): первый короткий блок, где громкость резко выше фона
 * в начале буфера. Нужен, чтобы знать момент удара точнее, чем «кадр экрана» (~16 мс).
 */
export function attackIndex(buf: Float32Array, block = 64): number {
  const n = Math.floor(buf.length / block);
  if (n < 4) return buf.length - 1;
  const env = new Float32Array(n);
  for (let b = 0; b < n; b++) {
    let s = 0;
    for (let i = b * block; i < (b + 1) * block; i++) s += buf[i] * buf[i];
    env[b] = Math.sqrt(s / block);
  }
  let max = 0;
  for (const v of env) max = Math.max(max, v);
  const base = [...env.slice(0, Math.max(2, n >> 2))].sort((a, b) => a - b)[Math.max(0, (n >> 3) - 1)] ?? 0;
  const thr = Math.max(base * 3, max * 0.3);
  for (let b = 1; b < n; b++) if (env[b] >= thr) return b * block;
  return buf.length - 1;
}

/** Медиана (для подстройки задержки: устойчива к случайным промахам). */
export function median(xs: number[]): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/**
 * Доля низких частот (до ~500 Гц) в отрезке buf[from..]: у удара по струнам она большая, у щелчка
 * метронома (писк 1–2 кГц), который микрофон слышит из колонок, — маленькая.
 */
export function lowShare(buf: Float32Array, from: number, sampleRate: number, cutoff = 500): number {
  const a = 1 - Math.exp((-2 * Math.PI * cutoff) / sampleRate);
  let y = 0;
  let low = 0;
  let all = 0;
  for (let i = Math.max(0, from); i < buf.length; i++) {
    y += a * (buf[i] - y);
    low += y * y;
    all += buf[i] * buf[i];
  }
  return all > 0 ? Math.sqrt(low / all) : 0;
}
