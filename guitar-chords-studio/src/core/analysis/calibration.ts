// Калибровка под гитару и микрофон: пользователь по очереди играет открытые струны.
// Что узнаём:
//  • строй каждой струны (центы от эталона) — подсказать подстроить и учесть общий сдвиг;
//  • как микрофон передаёт басы: у дешёвых микрофонов основной тон низких струн почти пропадает,
//    остаются обертоны — и распознавание путает ноту с её октавой. По каждой струне считаем,
//    во сколько раз основной тон слабее обертонов, и строим кривую усиления по полутонам.

import { detectPitch, freqToMidi } from './pitch';
import { SEMI_COUNT, SEMI_LO } from './dsp';

export interface StringCalibration {
  /** Нота открытой струны (с учётом каподастра). */
  openMidi: number;
  /** Отклонение строя, центы (null — высоту не удалось определить). */
  cents: number | null;
  /** Основной тон относительно обертонов (1 — как ожидается, 0,2 — микрофон «съедает» бас). */
  fundamental: number;
  /** Громкость струны относительно самой громкой (0..1). */
  level: number;
}

export interface Calibration {
  date: number;
  /** Общий сдвиг строя, центы (медиана по струнам). */
  tuningCents: number;
  /** Усиление по полутонам спектра (SEMI_LO..SEMI_HI). */
  gains: number[];
  strings: StringCalibration[];
}

const RATIO_TARGET = 0.9;
/** Подъём басов — не больше чем в 1,5 раза: сильнее — и басовые обертоны начинали «перекрикивать» аккорд. */
const MAX_GAIN = 1.5;

/** Замер одной открытой струны: звук (для точной высоты) и спектр по полутонам. */
export function measureOpenString(
  buf: Float32Array,
  sampleRate: number,
  semi: Float32Array,
  openMidi: number,
): Omit<StringCalibration, 'level'> & { energy: number; heardMidi: number | null } {
  const p = detectPitch(buf, sampleRate, 50, 1200);
  let cents: number | null = null;
  let heardMidi: number | null = null;
  if (p && p.clarity > 0.5) {
    let m = freqToMidi(p.freq);
    heardMidi = Math.round(m);
    // YIN иногда ошибается на октаву — сравниваем с ближайшей октавой ожидаемой ноты.
    for (const k of [-12, 12]) if (Math.abs(m + k - openMidi) < Math.abs(m - openMidi)) m += k;
    if (Math.abs(m - openMidi) <= 1) cents = Math.round((m - openMidi) * 100);
  }
  const at = (m: number) => {
    const i = m - SEMI_LO;
    return i >= 0 && i < semi.length ? semi[i] : 0;
  };
  const fund = at(openMidi);
  const harm = (at(openMidi + 12) + at(openMidi + 19)) / 2;
  return { openMidi, cents, heardMidi, fundamental: harm > 0 ? fund / harm : 1, energy: fund + harm };
}

/** Собрать калибровку из замеров всех струн. */
export function buildCalibration(measured: (Omit<StringCalibration, 'level'> & { energy: number })[]): Calibration {
  const maxE = Math.max(...measured.map((m) => m.energy), 1e-9);
  const strings = measured.map(({ openMidi, cents, fundamental, energy }) => ({ openMidi, cents, fundamental, level: energy / maxE }));
  const cents = strings.map((s) => s.cents).filter((c): c is number => c != null);
  const sorted = [...cents].sort((a, b) => a - b);
  const tuningCents = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
  // Точки кривой: на основном тоне каждой струны — во сколько раз поднять (только вверх).
  const points = strings
    .map((s) => ({ midi: s.openMidi, g: Math.min(MAX_GAIN, Math.max(1, RATIO_TARGET / Math.max(1e-3, s.fundamental))) }))
    .sort((a, b) => a.midi - b.midi);
  const gains = new Array(SEMI_COUNT).fill(1);
  if (points.length) {
    const top = points[points.length - 1];
    for (let i = 0; i < SEMI_COUNT; i++) {
      const m = SEMI_LO + i;
      let g: number;
      if (m <= points[0].midi) g = points[0].g;
      else if (m >= top.midi) g = 1 + (top.g - 1) * Math.max(0, 1 - (m - top.midi) / 12);
      else {
        const k = points.findIndex((p) => p.midi >= m);
        const a = points[k - 1];
        const b = points[k];
        g = a.g + ((b.g - a.g) * (m - a.midi)) / Math.max(1, b.midi - a.midi);
      }
      gains[i] = Math.round(g * 100) / 100;
    }
  }
  return { date: Date.now(), tuningCents, gains, strings };
}

/** Применить калибровку к спектру по полутонам (на месте). */
export function applyGains(semi: Float32Array, gains: readonly number[] | null | undefined) {
  if (!gains) return semi;
  // Старые калибровки поднимали басы до ×6 — ограничиваем и их.
  for (let i = 0; i < semi.length && i < gains.length; i++) semi[i] *= Math.min(MAX_GAIN, gains[i]);
  return semi;
}
