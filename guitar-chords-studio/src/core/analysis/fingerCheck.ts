// Проверка аппликатуры по звуку: какие струны аккорда звучат чисто, какие почти не слышны
// (струна приглушена пальцем) и не звенит ли лишнее (заглушенная струна, неверный лад).

import { detectNotes, SEMI_LO } from './dsp';
import { mod12 } from '../music/notes';

export interface ExpectedString {
  /** Номер струны (0 — басовая). */
  string: number;
  /** Нота, которая должна звучать; null — струна должна молчать. */
  midi: number | null;
  /** Нота открытой струны с учётом каподастра — чтобы узнать звон заглушенной струны. */
  openMidi: number;
}

export type StringStatus = 'ok' | 'weak' | 'missing' | 'wrong' | 'ringing' | 'silent';

export interface StringVerdict {
  string: number;
  midi: number | null;
  status: StringStatus;
  /** Сила ноты относительно самой громкой ноты аккорда (0..1). */
  level: number;
  /** Для 'wrong': какая нота звучит вместо нужной. */
  heard?: number;
}

export interface FingerCheckResult {
  strings: StringVerdict[];
  /** Лишние ноты (не из аккорда). */
  extras: number[];
  /** Сколько струн звучат как надо, из скольких. */
  good: number;
  total: number;
}

/** Обертоны струны, которые вычитаются из спектра перед оценкой более высоких нот (с запасом — чуть меньше типичных). */
const PARTIALS: [number, number][] = [
  [12, 0.5],
  [19, 0.3],
  [24, 0.2],
];

/**
 * Сила каждой ноты-кандидата: идём от баса вверх, берём основной тон и вычитаем его обертоны.
 * Иначе октава нижней струны «заполняет» приглушённую верхнюю (C3 и C4 в до мажоре).
 */
export function noteStrengths(semi: ArrayLike<number>, midis: number[]): Map<number, number> {
  const s = Float32Array.from(semi);
  const at = (m: number) => m - SEMI_LO;
  const out = new Map<number, number>();
  for (const m of [...new Set(midis)].sort((a, b) => a - b)) {
    const i = at(m);
    const f = i >= 0 && i < s.length ? Math.max(0, s[i]) : 0;
    out.set(m, f);
    for (const [off, w] of PARTIALS) if (i + off >= 0 && i + off < s.length) s[i + off] = Math.max(0, s[i + off] - f * w);
  }
  return out;
}

export function checkFingering(semi: ArrayLike<number>, expected: ExpectedString[]): FingerCheckResult {
  const playing = expected.filter((e): e is ExpectedString & { midi: number } => e.midi != null);
  const playMidis = new Set(playing.map((e) => e.midi));
  const chordPcs = new Set(playing.map((e) => mod12(e.midi)));
  const mutedOpen = expected.filter((e) => e.midi == null && !playMidis.has(e.openMidi)).map((e) => e.openMidi);
  const strengths = noteStrengths(semi, [...playMidis, ...mutedOpen]);
  const ref = Math.max(1e-9, ...playing.map((e) => strengths.get(e.midi)!));

  const strings: StringVerdict[] = expected.map((e) => {
    if (e.midi == null) {
      // Заглушенная струна «звенит», если слышна её открытая нота (которой нет среди нот аккорда).
      const lvl = playMidis.has(e.openMidi) ? 0 : strengths.get(e.openMidi)! / ref;
      return { string: e.string, midi: null, status: lvl > 0.3 ? 'ringing' : 'silent', level: Math.min(1, lvl) };
    }
    // У низких струн основной тон в записи всегда тише — делаем поправку.
    const lvl = (strengths.get(e.midi)! / ref) * (e.midi < 50 ? 2.5 : e.midi < 57 ? 1.5 : 1);
    return { string: e.string, midi: e.midi, status: lvl < 0.05 ? 'missing' : lvl < 0.2 ? 'weak' : 'ok', level: Math.min(1, lvl) };
  });
  const found = detectNotes(Float32Array.from(semi), 10, 84);
  const top = found[0]?.strength ?? 0;
  const extras = found.filter((n) => !chordPcs.has(mod12(n.midi)) && n.strength > top * 0.25).map((n) => n.midi);

  // Лишняя нота на полтона–тон от ноты струны: скорее всего, эта струна не прижата или прижата не на том ладу.
  for (const x of extras) {
    let best: StringVerdict | null = null;
    for (const v of strings)
      if (v.midi != null && Math.abs(v.midi - x) <= 2 && (!best || Math.abs(v.midi - x) < Math.abs(best.midi! - x))) best = v;
    if (best) Object.assign(best, { status: 'wrong', heard: x });
  }

  const good = strings.filter((s) => s.status === 'ok' || s.status === 'silent').length;
  return { strings, extras, good, total: strings.length };
}
