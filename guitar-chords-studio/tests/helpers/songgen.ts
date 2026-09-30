// Синтетические «трудные» песни для замера точности разбора: гитара (бой), бас, ударные,
// «вокал» с вибрато и неаккордовыми нотами, шум, расстройка всей записи.

import { parseChordSymbol } from '../../src/core/music/chordParse';
import { chordPitchClasses } from '../../src/core/music/chordParse';

export const GSR = 22050;

function rng(seed: number) {
  let s = seed;
  return () => ((s = (s * 16807) % 2147483647) / 2147483647) * 2 - 1;
}

function addTone(out: Float32Array, t0: number, dur: number, freq: number, amp: number, harmonics: number[], decay: number, vibrato = 0) {
  const start = Math.floor(t0 * GSR);
  const n = Math.floor(dur * GSR);
  for (let h = 0; h < harmonics.length; h++) {
    const a = amp * harmonics[h];
    if (!a || freq * (h + 1) > GSR / 2.2) continue;
    let phase = h;
    for (let i = 0; i < n && start + i < out.length; i++) {
      const t = i / GSR;
      const f = freq * (h + 1) * (1 + vibrato * Math.sin(2 * Math.PI * 5.5 * t));
      phase += (2 * Math.PI * f) / GSR;
      const env = Math.exp(-decay * (1 + h * 0.4) * t) * Math.min(1, i / (GSR * 0.005));
      out[start + i] += a * env * Math.sin(phase);
    }
  }
}

const hz = (midi: number, cents: number) => 440 * Math.pow(2, (midi - 69 + cents / 100) / 12);

/** Голоса аккорда для гитары: тоника в басу, дальше тоны аккорда в диапазоне E2–E4. */
function voicing(symbol: string): number[] {
  const p = parseChordSymbol(symbol)!;
  const pcs = chordPitchClasses(p.rootPc, p.template).map((x) => x.pc);
  let root = 40 + ((p.rootPc - 4 + 12) % 12);
  if (root > 47) root -= 12;
  const notes = [root];
  let cur = root;
  for (let k = 0; notes.length < 6 && k < 30; k++) {
    cur++;
    if (pcs.includes(cur % 12) && cur - notes[notes.length - 1] >= 3) notes.push(cur);
  }
  return notes;
}

export interface SongSpec {
  chords: string[]; // по одному на такт (или полтакта при beatsPerChord=2)
  bpm: number;
  beatsPerChord: number;
  cents: number; // расстройка всей записи
  vocal: number; // громкость «вокала»
  drums: number;
  noise: number;
  seed: number;
}

export interface GeneratedSong {
  audio: Float32Array;
  /** Истинный аккорд на каждое время (сек) — функция. */
  truthAt: (t: number) => string;
  duration: number;
}

export function makeSong(spec: SongSpec): GeneratedSong {
  const beat = 60 / spec.bpm;
  const totalBeats = spec.chords.length * spec.beatsPerChord;
  const duration = totalBeats * beat + 0.5;
  const out = new Float32Array(Math.ceil(duration * GSR));
  const r = rng(spec.seed);
  const guitarH = [0.6, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08, 0.05];
  for (let b = 0; b < totalBeats; b++) {
    const t = b * beat;
    const sym = spec.chords[Math.floor(b / spec.beatsPerChord)];
    const notes = voicing(sym);
    // Бой: вниз на долю, вверх на полдоли (без баса).
    notes.forEach((m, i) => addTone(out, t + i * 0.012, beat * 1.2, hz(m, spec.cents), 0.05, guitarH, 3));
    notes.slice(2).forEach((m, i) => addTone(out, t + beat / 2 + i * 0.01, beat * 0.7, hz(m, spec.cents), 0.03, guitarH, 4));
    // Бас: тоника на первую долю аккорда и на каждую долю.
    addTone(out, t, beat * 0.95, hz(notes[0] - 12, spec.cents), 0.12, [1, 0.5, 0.3, 0.15], 1.5);
    // Ударные: бочка (1, 3), малый (2, 4), хай-хэт восьмыми.
    const s0 = Math.floor(t * GSR);
    for (let i = 0; i < GSR * 0.15 && s0 + i < out.length; i++) {
      const tt = i / GSR;
      if (b % 2 === 0) out[s0 + i] += spec.drums * 0.6 * Math.sin(2 * Math.PI * (50 + 80 * Math.exp(-30 * tt)) * tt) * Math.exp(-18 * tt);
      else out[s0 + i] += spec.drums * 0.35 * r() * Math.exp(-25 * tt);
    }
    for (const off of [0, beat / 2]) {
      const h0 = Math.floor((t + off) * GSR);
      for (let i = 0; i < GSR * 0.05 && h0 + i < out.length; i++) out[h0 + i] += spec.drums * 0.12 * r() * Math.exp((-90 * i) / GSR);
    }
    // «Вокал»: одна нота на долю, чаще из аккорда, иногда проходящая (по гамме), с вибрато.
    if (spec.vocal > 0) {
      const p = parseChordSymbol(sym)!;
      const pcs = chordPitchClasses(p.rootPc, p.template).map((x) => x.pc);
      const scale = [0, 2, 4, 5, 7, 9, 11];
      const pc = r() > -0.3 ? pcs[Math.floor(((r() + 1) / 2) * pcs.length) % pcs.length] : scale[Math.floor(((r() + 1) / 2) * 7) % 7];
      const midi = 60 + ((pc - 0 + 12) % 12) + (r() > 0.5 ? 12 : 0);
      addTone(out, t + 0.02, beat * 0.95, hz(midi, spec.cents), spec.vocal * 0.1, [1, 0.45, 0.25, 0.12, 0.06], 0.4, 0.006);
    }
  }
  for (let i = 0; i < out.length; i++) out[i] += spec.noise * 0.02 * r();
  const truthAt = (tt: number) => {
    const b = Math.floor(tt / beat);
    if (b < 0 || b >= totalBeats) return 'N';
    return spec.chords[Math.floor(b / spec.beatsPerChord)];
  };
  return { audio: out, truthAt, duration: totalBeats * beat };
}
