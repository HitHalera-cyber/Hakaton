// Режим «По струнам»: аккорд зажат, струны щиплются по одной от 6-й к 1-й.
// Каждый щипок — одна новая нота: она определяется по тому, что ДОБАВИЛОСЬ в спектре
// (прежние струны ещё звучат — их вычитаем). Затем щипки раскладываются по струнам:
// порядок известен (сверху вниз), лад = нота − нота открытой струны. Так получается точная
// аппликатура, а не «типичная форма аккорда».

import type { Frets } from '../music/fretboard';
import { SEMI_LO, detectNotes } from './dsp';

export interface Pluck {
  /** Услышанная нота (MIDI) или null — глухой щипок по заглушённой струне. */
  midi: number | null;
  /** Насколько щипок похож на чистую ноту (0..1). */
  clarity: number;
  /** Громкость ноты (прирост энергии на ноте и её обертонах). */
  energy?: number;
}

/** Сдвиги обертонов (полутона) для оценки «чистоты» ноты. */
const HARMONICS = [0, 12, 19, 24, 28, 31];

/**
 * Нота щипка по спектрам до и после него. lo..hi — какие ноты вообще можно сыграть на этом
 * инструменте (от открытой басовой струны до верхнего лада 1-й).
 */
export function pluckFromSpectra(pre: Float32Array, post: Float32Array, lo: number, hi: number, minClarity = 0.3): Pluck {
  const n = post.length;
  const d = new Float32Array(n);
  let total = 0;
  for (let i = 0; i < n; i++) {
    d[i] = Math.max(0, post[i] - pre[i] * 1.05);
    total += d[i];
  }
  if (total <= 0) return { midi: null, clarity: 0 };
  const found = detectNotes(d, 3, Math.min(hi, SEMI_LO + n - 1)).filter((x) => x.midi >= lo && x.midi <= hi);
  if (!found.length) return { midi: null, clarity: 0 };
  const midi = found[0].midi;
  // Чистота: доля прироста энергии, которая приходится на ноту и её обертоны (±1 полутон — запас на строй).
  const i0 = midi - SEMI_LO;
  let tonal = 0;
  const used = new Set<number>();
  for (const off of HARMONICS)
    for (const k of [-1, 0, 1]) {
      const j = i0 + off + k;
      if (j >= 0 && j < n && !used.has(j)) {
        used.add(j);
        tonal += d[j];
      }
    }
  const clarity = Math.min(1, tonal / total);
  return clarity >= minClarity ? { midi, clarity, energy: tonal } : { midi: null, clarity, energy: tonal };
}

export interface StringFingering {
  /** Лад на каждой струне (0 — басовая), null — струна не звучит. */
  frets: Frets;
  /** На какую струну пришёлся каждый щипок. */
  strings: number[];
  /** Уверенность в раскладке 0..1 (насколько лучший вариант лучше следующего). */
  confidence: number;
}

/** Все возрастающие наборы из k струн. */
function combos(n: number, k: number, from = 0): number[][] {
  if (k === 0) return [[]];
  const out: number[][] = [];
  for (let s = from; s <= n - k; s++) for (const rest of combos(n, k - 1, s + 1)) out.push([s, ...rest]);
  return out;
}

/**
 * Разложить щипки по струнам. Щипки идут от басовой струны к тонкой; если какую-то струну
 * пропустили (не задели), выбирается раскладка, удобная для руки: разброс ладов ≤ 4–5,
 * без «дыр» посередине.
 */
export function solveFingering(plucks: Pluck[], tuning: number[], capo = 0, maxFret = 15): StringFingering | null {
  const n = tuning.length;
  const list = plucks.slice(0, n);
  if (!list.length) return null;
  const scored: { frets: Frets; strings: number[]; cost: number }[] = [];
  for (const strings of combos(n, list.length)) {
    const frets: Frets = new Array(n).fill(null);
    let ok = true;
    strings.forEach((s, j) => {
      const m = list[j].midi;
      if (m == null) return; // глухой щипок — струна заглушена
      const f = m - tuning[s];
      if (f < capo || f > maxFret + capo) ok = false;
      else frets[s] = f;
    });
    if (!ok) continue;
    const fretted = frets.filter((f): f is number => f != null && f > capo);
    const span = fretted.length ? Math.max(...fretted) - Math.min(...fretted) : 0;
    if (span > 5) continue;
    // Пропуски внутри (между задетыми струнами) — маловероятны; снаружи — обычное дело (x32010).
    const first = strings[0];
    const last = strings[strings.length - 1];
    const inner = last - first + 1 - strings.length;
    const outer = n - (last - first + 1);
    const cost = inner * 4 + outer * 1 + span * 0.6 + (fretted.length ? Math.min(...fretted) - capo : 0) * 0.12;
    scored.push({ frets, strings, cost });
  }
  if (!scored.length) return null;
  scored.sort((a, b) => a.cost - b.cost);
  const gap = scored.length > 1 ? scored[1].cost - scored[0].cost : 10;
  return { frets: scored[0].frets, strings: scored[0].strings, confidence: Math.max(0, Math.min(1, gap / 2)) };
}

/** Табулатурная запись аппликатуры: x32010 (лады больше 9 — в скобках). */
export function fretsToTab(frets: Frets): string {
  return frets.map((f) => (f == null ? 'x' : f > 9 ? `(${f})` : String(f))).join('');
}

/**
 * Ловит щипки в режиме «По струнам». Три признака: скачок громкости (басовые струны), всплеск
 * верхов (щипок поверх звенящих струн) и появление новой ноты в спектре (последний довод, когда
 * первые два не сработали). Для каждого щипка запоминает спектр «до» — чтобы потом вычесть.
 */
export class PluckTracker {
  private history: { t: number; semi: Float32Array }[] = [];
  private lastPluck = -10;
  private floor = -1;
  /** Наименьший промежуток между щипками, с. */
  minGap = 0.22;

  /** Спектр не позже момента t (самый поздний из таких). */
  private semiAt(t: number): Float32Array | null {
    for (let i = this.history.length - 1; i >= 0; i--) if (this.history[i].t <= t) return this.history[i].semi;
    return this.history[0]?.semi ?? null;
  }

  /**
   * Новый кадр: t — время, semi — спектр по полутонам сейчас, quick — сработал быстрый признак
   * (громкость или верха). Возвращает спектр «до щипка», если щипок случился.
   */
  feed(t: number, semi: Float32Array, quick: boolean): { at: number; pre: Float32Array } | null {
    this.history.push({ t, semi });
    while (this.history.length && this.history[0].t < t - 0.6) this.history.shift();
    // Фон: самая тихая энергия за последние секунды (медленно поднимается, быстро опускается).
    let total = 0;
    for (let i = 0; i < semi.length; i++) total += semi[i];
    this.floor = this.floor < 0 || total < this.floor ? total : this.floor * 1.004;
    if (t - this.lastPluck < this.minGap) return null;
    if (quick) {
      this.lastPluck = t;
      return { at: t, pre: this.semiAt(t - 0.02) ?? semi };
    }
    // Новая нота в спектре: прирост за 0,12 с, сосредоточенный в нескольких полутонах.
    // Пока окно анализа (~0,34 с) ещё заполняется прошлым щипком, его же рост не считаем новым.
    if (t - 0.12 < this.lastPluck + 0.38) return null;
    const old = this.semiAt(t - 0.12);
    if (!old) return null;
    let inc = 0;
    let base = 0;
    let peak = 0;
    for (let i = 0; i < semi.length; i++) {
      const d = semi[i] - old[i] * 1.15;
      if (d > 0) {
        inc += d;
        if (d > peak) peak = d;
      }
      base += old[i];
    }
    // В тишине шум колеблется — новой нотой считаем только то, что заметно громче фона.
    if (base > 0 && inc / base > 0.3 && peak / inc > 0.2 && inc > this.floor * 1.5 && this.history[0].t <= t - 0.5) {
      this.lastPluck = t - 0.12;
      return { at: t - 0.12, pre: this.semiAt(t - 0.3) ?? old };
    }
    return null;
  }

  reset() {
    this.history = [];
    this.floor = -1;
  }
}
