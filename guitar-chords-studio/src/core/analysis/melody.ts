// Подбор мелодии: поток «высота тона по кадрам» превращается в ноты, ноты — в табулатуру.

import { midiName } from '../music/notes';

export interface MelodyNote {
  midi: number;
  start: number;
  end: number;
}

/** Нота начинается, когда одна и та же высота держится несколько кадров, и кончается на тишине или смене. */
export class MelodyTracker {
  notes: MelodyNote[] = [];
  private cand: { midi: number; since: number; frames: number } | null = null;
  private current: MelodyNote | null = null;
  private lastPitched = -1;

  constructor(
    private minFrames = 3,
    private releaseSec = 0.08,
    private minDur = 0.08,
  ) {}

  /** midi — ближайшая нота кадра или null, если тона нет; onset — был удар по струне. */
  feed(midi: number | null, time: number, onset = false) {
    if (midi == null) {
      if (this.current && time - this.lastPitched > this.releaseSec) this.finish(this.lastPitched);
      this.cand = null;
      return;
    }
    this.lastPitched = time;
    // Новый удар по той же ноте — повтор ноты. Удар, пойманный сразу после начала ноты, — это она же
    // (громкость по кадру растёт чуть позже, чем появляется высота тона).
    const retrigger = onset && this.current?.midi === midi && time - this.current.start > 0.15;
    if (retrigger) {
      this.finish(time);
      this.current = { midi, start: time, end: time };
      this.cand = null;
      return;
    }
    if (this.current && this.current.midi === midi) {
      this.current.end = time;
      this.cand = null;
      return;
    }
    if (!this.cand || this.cand.midi !== midi) this.cand = { midi, since: time, frames: 1 };
    else this.cand.frames++;
    if (this.cand.frames >= this.minFrames) {
      if (this.current) this.finish(this.cand.since);
      this.current = { midi, start: this.cand.since, end: time };
      this.cand = null;
    }
  }

  /** Закончить текущую ноту (например, при остановке). */
  flush() {
    if (this.current) this.finish(this.current.end);
  }

  private finish(end: number) {
    const n = this.current!;
    n.end = Math.max(n.end, end);
    if (n.end - n.start >= this.minDur) this.notes.push(n);
    this.current = null;
  }
}

export interface TabPos {
  string: number;
  fret: number;
}

/**
 * Расстановка нот мелодии по струнам: каждая нота — туда, где рука ближе к предыдущей позиции,
 * при равенстве — ниже по грифу. tuning — открытые струны от басовой.
 */
export function placeOnFretboard(notes: number[], tuning: number[], capo = 0, maxFret = 15): (TabPos | null)[] {
  let hand = capo;
  return notes.map((midi) => {
    const options: TabPos[] = [];
    tuning.forEach((open, s) => {
      const fret = midi - open;
      if (fret >= capo && fret <= maxFret) options.push({ string: s, fret });
    });
    if (!options.length) return null;
    const cost = (p: TabPos) => (p.fret === capo ? 0.5 : Math.abs(p.fret - hand)) + p.fret * 0.05;
    const best = options.reduce((a, b) => (cost(b) < cost(a) ? b : a));
    if (best.fret > capo) hand = best.fret;
    return best;
  });
}

/** Табулатура текстом: верхняя строка — тонкая струна. */
export function melodyTab(notes: number[], tuning: number[], capo = 0): string {
  const pos = placeOnFretboard(notes, tuning, capo);
  const names = tuning.map((m) => midiName(m).replace(/-?\d+$/, ''));
  const width = Math.max(...names.map((n) => n.length));
  const rows = tuning.map(() => [] as string[]);
  pos.forEach((p) => {
    const w = p ? String(p.fret).length : 1;
    rows.forEach((r, s) => r.push((p && p.string === s ? String(p.fret) : '-'.repeat(w)) + '-'));
  });
  return rows
    .map((r, s) => `${names[s].padEnd(width)}|-${r.join('')}|`)
    .reverse()
    .join('\n');
}
