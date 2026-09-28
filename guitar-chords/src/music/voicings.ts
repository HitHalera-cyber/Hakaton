// Генератор аппликатур аккорда по всему грифу (для справочника и «аккордов тональности»).
//
// Для каждого положения руки (окно в 4 лада) перебираются варианты на каждой струне:
// не играть, открытая струна (если это нота аккорда) или лад окна с нотой аккорда.
// Отбрасываются варианты без обязательных нот, с неправильным басом и с неиграбельной
// аппликатурой (больше 4 пальцев с учётом баррэ). Остальные оцениваются: больше звучащих
// струн, без «дыр» внутри аккорда, меньше пальцев, ниже по грифу — лучше.

import type { ChordTemplate } from './chords';
import { chordPitchClasses } from './chordParse';
import { boardFromFrets, type Frets } from './fretboard';
import { computeFingering } from './fingering';
import { mod12 } from './notes';
import { FRET_COUNT } from './tunings';

export interface Voicing {
  frets: Frets;
  /** Самый нижний зажатый лад (0 — только открытые струны). */
  position: number;
  score: number;
}

interface Options {
  capo?: number;
  bassPc?: number;
  limit?: number;
}

export function generateVoicings(rootPc: number, template: ChordTemplate, tuning: number[], opts: Options = {}): Voicing[] {
  const capo = opts.capo ?? 0;
  const bassPc = opts.bassPc ?? rootPc;
  const limit = opts.limit ?? 12;
  const tones = chordPitchClasses(rootPc, template);
  const chordPcs = new Set(tones.map((t) => t.pc));
  const required = tones.filter((t) => !t.optional).map((t) => t.pc);
  const n = tuning.length;
  const minStrings = Math.min(n, Math.max(3, Math.min(tones.length, n >= 6 ? 4 : 3)));

  const found = new Map<string, Voicing>();

  for (let w = capo; w <= FRET_COUNT - 3; w++) {
    const lo = Math.max(capo + 1, w);
    const hi = Math.min(FRET_COUNT, w + 3);
    const options: (number | null)[][] = tuning.map((open) => {
      const opt: (number | null)[] = [null];
      if (chordPcs.has(mod12(open + capo))) opt.push(capo);
      for (let f = lo; f <= hi; f++) if (chordPcs.has(mod12(open + f))) opt.push(f);
      return opt;
    });

    const cur: Frets = new Array(n).fill(null);
    const walk = (s: number) => {
      if (s === n) {
        evaluate(cur);
        return;
      }
      for (const o of options[s]) {
        cur[s] = o;
        walk(s + 1);
      }
    };

    const evaluate = (frets: Frets) => {
      const sounding: { s: number; f: number; midi: number }[] = [];
      frets.forEach((f, s) => {
        if (f != null) sounding.push({ s, f, midi: tuning[s] + f });
      });
      if (sounding.length < minStrings) return;
      const pcs = new Set(sounding.map((x) => mod12(x.midi)));
      if (!required.every((pc) => pcs.has(pc))) return;
      const lowest = sounding.reduce((a, b) => (b.midi < a.midi ? b : a));
      if (mod12(lowest.midi) !== bassPc) return;

      const fretted = sounding.filter((x) => x.f > capo);
      const position = fretted.length ? Math.min(...fretted.map((x) => x.f)) : 0;
      // Окно должно реально использоваться (иначе один и тот же вариант повторится).
      if (fretted.length && position !== lo && w > capo) return;
      const key = frets.map((f) => (f == null ? 'x' : f)).join(',');
      if (found.has(key)) return;

      const fingering = computeFingering(boardFromFrets(frets, capo), capo);
      if (fingering.count > 4) return;

      const first = frets.findIndex((f) => f != null);
      const last = n - 1 - [...frets].reverse().findIndex((f) => f != null);
      let inner = 0;
      for (let s = first; s <= last; s++) if (frets[s] == null) inner++;
      const missingOptional = tones.filter((t) => t.optional && !pcs.has(t.pc)).length;
      const opens = sounding.length - fretted.length;

      let score = 0;
      score -= sounding.length * 2;
      score += inner * 4;
      score += missingOptional * 3;
      score += fingering.count * 0.6;
      score += fingering.barre ? 1.5 : 0;
      score += (position - capo) * 0.35;
      score -= position <= capo + 3 ? opens * 0.8 : 0;
      found.set(key, { frets: [...frets], position, score });
    };

    walk(0);
  }

  // Лучшие варианты, не больше двух на одно положение руки — чтобы охватить весь гриф.
  const all = [...found.values()].sort((a, b) => a.score - b.score);
  const perPosition = new Map<number, number>();
  const out: Voicing[] = [];
  for (const v of all) {
    const k = perPosition.get(v.position) ?? 0;
    if (k >= 2) continue;
    perPosition.set(v.position, k + 1);
    out.push(v);
    if (out.length >= limit) break;
  }
  return out.sort((a, b) => a.position - b.position || a.score - b.score);
}

/** Табулатурная запись: «x32010», для ладов ≥ 10 — через пробел. */
export function fretsToString(frets: Frets): string {
  const big = frets.some((f) => f != null && f >= 10);
  return frets.map((f) => (f == null ? 'x' : String(f))).join(big ? ' ' : '');
}
