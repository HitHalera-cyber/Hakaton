// Автоподбор аппликатур для песни: из вариантов каждого аккорда выбирается цепочка,
// в которой рука меньше всего перемещается между соседними аккордами (динамическое программирование).

import { parseChordSymbol } from '../music/chordParse';
import type { Frets } from '../music/fretboard';
import { generateVoicings, type Voicing } from '../music/voicings';

/** Средний лад прижатых струн (0 для открытых аккордов). */
export function handPosition(frets: Frets): number {
  const pressed = frets.filter((f): f is number => f != null && f > 0);
  return pressed.length ? pressed.reduce((a, b) => a + b, 0) / pressed.length : 0;
}

/** «Стоимость» перехода между аппликатурами: сдвиг руки по грифу и число переставляемых пальцев. */
export function transitionCost(a: Frets, b: Frets): number {
  const move = Math.abs(handPosition(a) - handPosition(b));
  let changed = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) changed++;
  return move * 2 + changed * 0.5;
}

export function voicingOptions(symbol: string, tuning: number[], capo: number, limit = 6): Voicing[] {
  const p = parseChordSymbol(symbol);
  if (!p) return [];
  const list = generateVoicings(p.rootPc, p.template, tuning, { capo, bassPc: p.bassPc, limit });
  return list.length ? list : generateVoicings(p.rootPc, p.template, tuning, { capo, limit });
}

/**
 * Для последовательности аккордов песни выбрать аппликатуры с самыми удобными переходами.
 * Своё «удобство» есть и у самой аппликатуры (score генератора), переходы складываются по порядку песни.
 */
export function planVoicings(sequence: string[], tuning: number[], capo: number): Record<string, Frets> {
  const symbols = [...new Set(sequence)].filter((s) => voicingOptions(s, tuning, capo, 1).length);
  const options = new Map(symbols.map((s) => [s, voicingOptions(s, tuning, capo)]));
  const seq = sequence.filter((s) => options.has(s));
  if (!seq.length) return {};
  // Локальный поиск: начинаем с лучшего по отдельности варианта каждого аккорда
  // и меняем по одному аккорду, пока суммарная стоимость падает.
  const bestOwn = (s: string) => {
    const list = options.get(s)!;
    return list.reduce((bi, v, i) => (v.score < list[bi].score ? i : bi), 0);
  };
  const choice = new Map(symbols.map((s) => [s, bestOwn(s)]));
  // Собственное неудобство аппликатуры: у генератора чем меньше score, тем лучше; приводим к 0..6.
  const scores = [...options.values()].flat().map((v) => v.score);
  const lo = Math.min(...scores);
  const span = Math.max(...scores) - lo || 1;
  const total = () => {
    let cost = 0;
    for (const s of symbols) cost += ((options.get(s)![choice.get(s)!].score - lo) / span) * 6;
    for (let i = 1; i < seq.length; i++) {
      if (seq[i] === seq[i - 1]) continue;
      cost += transitionCost(options.get(seq[i - 1])![choice.get(seq[i - 1])!].frets, options.get(seq[i])![choice.get(seq[i])!].frets);
    }
    return cost;
  };
  let best = total();
  for (let round = 0; round < 6; round++) {
    let improved = false;
    for (const s of symbols) {
      let bestK = choice.get(s)!;
      for (let k = 0; k < options.get(s)!.length; k++) {
        if (k === bestK) continue;
        const prev = choice.get(s)!;
        choice.set(s, k);
        const c = total();
        if (c < best - 1e-9) {
          best = c;
          bestK = k;
          improved = true;
        } else choice.set(s, prev);
      }
      choice.set(s, bestK);
    }
    if (!improved) break;
  }
  return Object.fromEntries(symbols.map((s) => [s, options.get(s)![choice.get(s)!].frets]));
}
