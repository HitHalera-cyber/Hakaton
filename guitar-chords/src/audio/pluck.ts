// Запасной синтез гитарной струны (расширенный алгоритм Карплуса — Стронга).
// Используется, если сэмпл ноты не загрузился: звук есть всегда, даже без файлов сэмплов.

import { midiToFreq } from '../music/notes';

export interface PluckParams {
  /** Время затухания до −60 дБ для ноты A2 (сек). */
  t60: number;
  /** Яркость «щипка» 0..1. */
  brightness: number;
  /** Место щипка от подставки (доля длины струны). */
  pluckPos: number;
  /** Демпфирование высоких частот в петле (0.5 — стандарт, меньше — ярче). */
  damping: number;
}

export const PLUCK_PRESETS: Record<'acoustic' | 'nylon' | 'electric', PluckParams> = {
  acoustic: { t60: 5.5, brightness: 0.8, pluckPos: 0.13, damping: 0.5 },
  nylon: { t60: 4.0, brightness: 0.45, pluckPos: 0.2, damping: 0.5 },
  electric: { t60: 8.0, brightness: 0.95, pluckPos: 0.09, damping: 0.42 },
};

export function renderPluck(sampleRate: number, midi: number, p: PluckParams): Float32Array {
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
