// Разбор песни: какие аккорды звучат и когда.
//
// 1. Звук приводится к моно ~22 кГц и режется на кадры; по каждому кадру — хромаграмма
//    (ноты, найденные в спектре) и бас.
// 2. По огибающей атак находится темп и доли (динамическое программирование, метод Эллиса).
// 3. Хромаграммы усредняются по долям.
// 4. Для каждой доли оцениваются все аккорды словаря; скрытая марковская модель (алгоритм
//    Витерби) выбирает самую правдоподобную цепочку: аккорд обычно держится несколько долей,
//    поэтому случайные «вспышки» соседних аккордов отбрасываются.
// 5. Тональность — по профилям Крумхансла; каподастр — чтобы играть простыми открытыми формами.

import { buildModels, scoreModels } from './chordRecognition';
import { chordName } from '../music/chordParse';
import { CHORD_TEMPLATES } from '../music/chords';
import { SpectrumAnalyzer, bassSalience, chromaFromNotes, detectNotes, tuningFromVector } from './dsp';
import { mod12 } from '../music/notes';

export interface SongFeatures {
  duration: number;
  bpm: number;
  /** Начала долей, секунды. */
  beats: number[];
  /** Хромаграмма на каждую долю (12 чисел). */
  chroma: number[][];
  bass: number[][];
  /** Громкость доли 0..1 (относительно самой громкой). */
  energy: number[];
  /** Строй записи относительно A = 440 Гц, центы. */
  tuningCents: number;
}

export interface ChordSegment {
  start: number;
  end: number;
  /** null — «без аккорда» (тишина, речь, ударные). */
  rootPc: number | null;
  templateId: string | null;
  symbol: string;
  nameRu: string;
  beats: number;
}

/** Уменьшить частоту дискретизации примерно до 22 кГц (усреднение соседних отсчётов). */
export function downsample(samples: Float32Array, sampleRate: number): { data: Float32Array; sampleRate: number } {
  const factor = Math.max(1, Math.floor(sampleRate / 22050));
  if (factor === 1) return { data: samples, sampleRate };
  const out = new Float32Array(Math.floor(samples.length / factor));
  for (let i = 0; i < out.length; i++) {
    let s = 0;
    for (let k = 0; k < factor; k++) s += samples[i * factor + k];
    out[i] = s / factor;
  }
  return { data: out, sampleRate: sampleRate / factor };
}

/** Огибающая атак: рост энергии в коротких окнах (шаг hop отсчётов). */
function onsetEnvelope(x: Float32Array, hop: number): Float32Array {
  const n = Math.floor(x.length / hop);
  const env = new Float32Array(n);
  let prev = 0;
  for (let i = 0; i < n; i++) {
    let e = 0;
    for (let k = 0; k < hop; k++) {
      // Разность соседних отсчётов подчёркивает высокие частоты — удары, щипки.
      const j = i * hop + k;
      const d = x[j] - (j > 0 ? x[j - 1] : 0);
      e += d * d;
    }
    const le = Math.log(1e-6 + e);
    env[i] = Math.max(0, le - prev);
    prev = le;
  }
  // Убираем медленный фон.
  const out = new Float32Array(n);
  const w = 16;
  let acc = 0;
  for (let i = 0; i < n; i++) {
    acc += env[i];
    if (i >= w) acc -= env[i - w];
    out[i] = Math.max(0, env[i] - acc / Math.min(i + 1, w));
  }
  return out;
}

/** Темп (периодичность атак) с предпочтением 80–160 уд/мин. */
function estimatePeriod(env: Float32Array, framesPerSec: number): number {
  const minLag = Math.floor((framesPerSec * 60) / 200);
  const maxLag = Math.ceil((framesPerSec * 60) / 55);
  let best = minLag;
  let bestV = -Infinity;
  for (let lag = minLag; lag <= maxLag && lag < env.length; lag++) {
    let s = 0;
    for (let i = lag; i < env.length; i++) s += env[i] * env[i - lag];
    s /= env.length - lag;
    const bpm = (60 * framesPerSec) / lag;
    const prior = Math.exp(-0.5 * Math.pow(Math.log2(bpm / 115) / 0.7, 2));
    const v = s * prior;
    if (v > bestV) {
      bestV = v;
      best = lag;
    }
  }
  return best;
}

/** Доли: динамическое программирование по огибающей атак (Ellis, 2007). */
function trackBeats(env: Float32Array, period: number): number[] {
  const n = env.length;
  const score = new Float32Array(n);
  const back = new Int32Array(n).fill(-1);
  const tightness = 100;
  for (let t = 0; t < n; t++) {
    let bestPrev = -1;
    let bestVal = 0;
    const from = Math.max(0, Math.round(t - 2 * period));
    const to = Math.round(t - period / 2);
    for (let p = from; p <= to; p++) {
      const v = score[p] - tightness * Math.pow(Math.log((t - p) / period), 2);
      if (bestPrev < 0 || v > bestVal) {
        bestVal = v;
        bestPrev = p;
      }
    }
    score[t] = env[t] + (bestPrev >= 0 ? Math.max(0, bestVal) : 0);
    back[t] = bestPrev >= 0 && bestVal > 0 ? bestPrev : -1;
  }
  // Конец — лучший счёт в последнем периоде.
  let t = n - 1;
  for (let i = Math.max(0, Math.floor(n - period)); i < n; i++) if (score[i] > score[t]) t = i;
  const beats: number[] = [];
  while (t >= 0) {
    beats.push(t);
    t = back[t];
  }
  return beats.reverse();
}

export function extractFeatures(input: Float32Array, inputRate: number, onProgress?: (p: number) => void): SongFeatures {
  const { data, sampleRate } = downsample(input, inputRate);
  const duration = data.length / sampleRate;

  // --- Доли ---
  const onsetHop = 256;
  const env = onsetEnvelope(data, onsetHop);
  const framesPerSec = sampleRate / onsetHop;
  const period = estimatePeriod(env, framesPerSec);
  let beatFrames = trackBeats(env, period);
  if (beatFrames.length < 4) {
    beatFrames = [];
    for (let t = 0; t < env.length; t += period) beatFrames.push(Math.round(t));
  }
  const beats = beatFrames.map((f) => f / framesPerSec);
  if (beats[0] > 0.05) beats.unshift(0);
  const bpm = Math.round((60 * framesPerSec) / period);
  onProgress?.(0.15);

  // --- Строй записи: многие песни записаны не точно в A = 440 Гц ---
  const size = 8192;
  const hop = 2048;
  const probe = new SpectrumAnalyzer(size, sampleRate);
  let tx = 0;
  let ty = 0;
  const probes = Math.max(1, Math.floor((data.length - size) / hop));
  const step = Math.max(1, Math.floor(probes / 150));
  for (let k = 0; k < probes; k += step) {
    const [x, y] = probe.tuningVector(data, k * hop);
    tx += x;
    ty += y;
  }
  const tuning = tuningFromVector(tx, ty);

  // --- Хромаграммы кадров ---
  const an = new SpectrumAnalyzer(size, sampleRate, tuning);
  const raw: { t: number; semi: Float32Array; rms: number }[] = [];
  const total = Math.max(1, Math.floor((data.length - size) / hop));
  for (let i = 0, k = 0; i + size <= data.length; i += hop, k++) {
    const { semi, rms } = an.semitones(data, i);
    raw.push({ t: (i + size / 2) / sampleRate, semi, rms });
    if (k % 50 === 0) onProgress?.(0.15 + 0.6 * (k / total));
  }

  // --- Гармоника отдельно от ударных (медианные фильтры, HPSS) ---
  // Гармоническое звучит долго на одной ноте (медиана по времени), удар — широкополосный
  // и короткий (медиана по частоте). Маска оставляет в спектре гармоническую часть.
  const harmonic = hpssMask(
    raw.map((r) => r.semi),
    5,
    9,
  );
  const frames: { t: number; chroma: Float32Array; bass: Float32Array; rms: number }[] = raw.map((r, k) => {
    const semi = harmonic[k];
    const { chroma } = chromaFromNotes(detectNotes(semi, 8, 76));
    if (k % 50 === 0) onProgress?.(0.75 + 0.2 * (k / raw.length));
    return { t: r.t, chroma, bass: bassSalience(semi), rms: r.rms };
  });

  // --- Усреднение по долям ---
  const chroma: number[][] = [];
  const bass: number[][] = [];
  const energy: number[] = [];
  let fi = 0;
  for (let b = 0; b < beats.length; b++) {
    const start = beats[b];
    const end = b + 1 < beats.length ? beats[b + 1] : duration;
    const c = new Array(12).fill(0);
    const bs = new Array(12).fill(0);
    let e = 0;
    let count = 0;
    while (fi < frames.length && frames[fi].t < start) fi++;
    for (let j = fi; j < frames.length && frames[j].t < end; j++) {
      for (let p = 0; p < 12; p++) {
        c[p] += frames[j].chroma[p];
        bs[p] += frames[j].bass[p];
      }
      e += frames[j].rms;
      count++;
    }
    if (count === 0 && frames.length) {
      const near = frames[Math.min(fi, frames.length - 1)];
      for (let p = 0; p < 12; p++) {
        c[p] = near.chroma[p];
        bs[p] = near.bass[p];
      }
      e = near.rms;
      count = 1;
    }
    chroma.push(c.map((v) => v / Math.max(1, count)));
    bass.push(bs.map((v) => v / Math.max(1, count)));
    energy.push(e / Math.max(1, count));
  }
  const maxE = Math.max(1e-9, ...energy);
  onProgress?.(1);
  return { duration, bpm, beats, chroma, bass, energy: energy.map((e) => e / maxE), tuningCents: Math.round(tuning * 100) };
}

function median(values: number[]): number {
  const v = [...values].sort((a, b) => a - b);
  return v[v.length >> 1];
}

/** Мягкая маска HPSS: спектр × H² / (H² + P²), H — медиана по времени, P — по частоте. */
export function hpssMask(spec: Float32Array[], timeWin = 9, freqWin = 9): Float32Array[] {
  const T = spec.length;
  if (!T) return [];
  const F = spec[0].length;
  const ht = timeWin >> 1;
  const hf = freqWin >> 1;
  return spec.map((frame, t) => {
    const out = new Float32Array(F);
    for (let f = 0; f < F; f++) {
      const col: number[] = [];
      for (let k = Math.max(0, t - ht); k <= Math.min(T - 1, t + ht); k++) col.push(spec[k][f]);
      const row: number[] = [];
      for (let k = Math.max(0, f - hf); k <= Math.min(F - 1, f + hf); k++) row.push(frame[k]);
      const h = median(col);
      const p = median(row);
      const h2 = h * h;
      out[f] = frame[f] * (h2 / (h2 + p * p + 1e-12));
    }
    return out;
  });
}

/**
 * Цепочка аккордов по признакам песни (Витерби). vocab — id шаблонов аккордов.
 * minBeats — минимальная длина аккорда в долях: более короткие «вспышки» (шум, проходящие ноты,
 * вокал) поглощаются соседями, чтобы аккорд на грифе не дёргался.
 */
export function decodeChords(f: SongFeatures, vocab: readonly string[], minBeats = 2): ChordSegment[] {
  // Темп иногда находится вдвое быстрее настоящего — тогда «доля» вдвое короче, и та же
  // стабильность в долях сглаживала бы вдвое меньше. Считаем её по времени (доля при ~110 уд/мин).
  const beats = Math.max(1, Math.round(minBeats * Math.max(1, f.bpm / 110)));
  return smoothSegments(viterbi(f, vocab, beats), beats);
}

export let KEY_BONUS = 0.02;
export const setKeyBonus = (v: number) => (KEY_BONUS = v);

const isMinor = (templateId: string) => {
  const t = CHORD_TEMPLATES.find((x) => x.id === templateId);
  return Boolean(t && t.degrees.includes('b3') && !t.degrees.includes('3'));
};

/** Аккорды тональности (трезвучия + доминанта в миноре): «тоника:M|m». */
function diatonicChords(tonicPc: number, mode: 'major' | 'minor'): Set<string> {
  const major = mode === 'major' ? tonicPc : mod12(tonicPc + 3);
  const set = new Set([0, 5, 7].map((d) => `${mod12(major + d)}:M`).concat([2, 4, 9].map((d) => `${mod12(major + d)}:m`)));
  if (mode === 'minor') set.add(`${mod12(tonicPc + 7)}:M`); // гармонический минор: E в ля миноре
  return set;
}

function viterbi(f: SongFeatures, vocab: readonly string[], minBeats: number): ChordSegment[] {
  const models = buildModels(vocab);
  const S = models.length + 1; // последний — «без аккорда»
  const N = f.beats.length;
  if (N === 0) return [];
  // Аккорды тональности песни встречаются чаще — небольшой бонус (второй «проход» после тональности).
  const key = detectKey(f);
  const diatonic = diatonicChords(key.tonicPc, key.mode);
  const keyBonus = models.map((m) => (diatonic.has(`${m.rootPc}:${isMinor(m.template.id) ? 'm' : 'M'}`) ? KEY_BONUS : 0));
  const emit = (b: number): Float32Array => {
    const sc = scoreModels(f.chroma[b], f.bass[b], models);
    const out = new Float32Array(S);
    const sharp = 18;
    for (let k = 0; k < models.length; k++) out[k] = sharp * (sc[k] + keyBonus[k]);
    // «Без аккорда» — когда тихо или хромаграмма «плоская».
    const quiet = f.energy[b] < 0.04 || f.chroma[b].every((v) => v === 0);
    out[S - 1] = sharp * (quiet ? 1.2 : 0.55);
    return out;
  };
  // Чем выше требуемая стабильность, тем «дороже» смена аккорда.
  const pStay = minBeats >= 3 ? 0.93 : minBeats >= 2 ? 0.88 : 0.8;
  const stay = Math.log(pStay);
  const move = Math.log((1 - pStay) / (S - 1));
  let prev = emit(0);
  const back: Int32Array[] = [];
  for (let b = 1; b < N; b++) {
    const e = emit(b);
    let bestAll = 0;
    for (let k = 1; k < S; k++) if (prev[k] > prev[bestAll]) bestAll = k;
    const cur = new Float32Array(S);
    const bk = new Int32Array(S);
    for (let k = 0; k < S; k++) {
      const viaStay = prev[k] + stay;
      const viaMove = prev[bestAll] + move;
      if (viaStay >= viaMove || bestAll === k) {
        cur[k] = viaStay + e[k];
        bk[k] = k;
      } else {
        cur[k] = viaMove + e[k];
        bk[k] = bestAll;
      }
    }
    back.push(bk);
    prev = cur;
  }
  let state = 0;
  for (let k = 1; k < S; k++) if (prev[k] > prev[state]) state = k;
  const path = new Array<number>(N);
  path[N - 1] = state;
  for (let b = N - 1; b > 0; b--) {
    state = back[b - 1][state];
    path[b - 1] = state;
  }

  const segments: ChordSegment[] = [];
  for (let b = 0; b < N; b++) {
    const start = f.beats[b];
    const end = b + 1 < N ? f.beats[b + 1] : f.duration;
    const last = segments[segments.length - 1];
    if (last && path[b] === path[b - 1]) {
      last.end = end;
      last.beats++;
      continue;
    }
    if (path[b] === S - 1) {
      segments.push({ start, end, rootPc: null, templateId: null, symbol: 'N', nameRu: 'Без аккорда', beats: 1 });
    } else {
      const m = models[path[b]];
      const name = chordName(m.rootPc, m.template);
      segments.push({ start, end, rootPc: m.rootPc, templateId: m.template.id, symbol: name.symbol, nameRu: name.nameRu, beats: 1 });
    }
  }
  return segments;
}

/** Поглотить слишком короткие сегменты соседями (сначала самые короткие). */
export function smoothSegments(segments: ChordSegment[], minBeats: number): ChordSegment[] {
  const segs = segments.map((s) => ({ ...s }));
  for (;;) {
    let idx = -1;
    for (let i = 0; i < segs.length; i++) {
      if (segs.length > 1 && segs[i].beats < minBeats && (idx < 0 || segs[i].beats < segs[idx].beats)) idx = i;
    }
    if (idx < 0) break;
    const prev = segs[idx - 1];
    const next = segs[idx + 1];
    // Присоединяем к более длинному соседу (аккорд, который звучит дольше, вероятнее настоящий).
    const target = !prev ? next : !next ? prev : prev.beats >= next.beats ? prev : next;
    const s = segs[idx];
    target.start = Math.min(target.start, s.start);
    target.end = Math.max(target.end, s.end);
    target.beats += s.beats;
    segs.splice(idx, 1);
    // Соседи могли оказаться одинаковыми — склеиваем.
    for (let i = segs.length - 1; i > 0; i--) {
      if (segs[i].symbol === segs[i - 1].symbol) {
        segs[i - 1].end = segs[i].end;
        segs[i - 1].beats += segs[i].beats;
        segs.splice(i, 1);
      }
    }
  }
  return segs;
}

// ---------- Тональность ----------

const KK_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const KK_MINOR = [6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];

function corr(a: number[], b: number[]): number {
  const ma = a.reduce((x, y) => x + y, 0) / a.length;
  const mb = b.reduce((x, y) => x + y, 0) / b.length;
  let num = 0;
  let da = 0;
  let db = 0;
  for (let i = 0; i < a.length; i++) {
    num += (a[i] - ma) * (b[i] - mb);
    da += (a[i] - ma) ** 2;
    db += (b[i] - mb) ** 2;
  }
  return num / Math.sqrt(da * db || 1);
}

export function detectKey(f: SongFeatures): { tonicPc: number; mode: 'major' | 'minor' } {
  const total = new Array(12).fill(0);
  f.chroma.forEach((c, b) => c.forEach((v, i) => (total[i] += v * f.energy[b])));
  let best = { tonicPc: 0, mode: 'major' as 'major' | 'minor', r: -Infinity };
  for (let t = 0; t < 12; t++) {
    const rot = total.map((_, i) => total[mod12(i + t)]);
    const rMaj = corr(rot, KK_MAJOR);
    const rMin = corr(rot, KK_MINOR);
    if (rMaj > best.r) best = { tonicPc: t, mode: 'major', r: rMaj };
    if (rMin > best.r) best = { tonicPc: t, mode: 'minor', r: rMin };
  }
  return { tonicPc: best.tonicPc, mode: best.mode };
}

// ---------- Каподастр ----------

/** Аккорды, которые легко играть в открытой позиции (тоники по типам). */
const EASY: Record<string, number[]> = {
  maj: [0, 2, 4, 7, 9], // C D E G A
  min: [2, 4, 9], // Dm Em Am
  '7': [0, 2, 4, 7, 9, 11], // C7 D7 E7 G7 A7 B7
  m7: [2, 4, 9], // Dm7 Em7 Am7
  maj7: [0, 2, 5, 7, 9], // Cmaj7 Dmaj7 Fmaj7 Gmaj7 Amaj7
};

export interface CapoSuggestion {
  capo: number;
  /** Доля времени песни, которую можно играть простыми формами. */
  easyShare: number;
}

/** Лучшие положения каподастра (0–7) по простоте аппликатур. */
export function suggestCapo(segments: ChordSegment[]): CapoSuggestion[] {
  const chords = segments.filter((s) => s.rootPc != null);
  const total = chords.reduce((a, s) => a + (s.end - s.start), 0) || 1;
  const out: CapoSuggestion[] = [];
  for (let capo = 0; capo <= 7; capo++) {
    let easy = 0;
    for (const s of chords) {
      const shape = mod12(s.rootPc! - capo);
      if (EASY[s.templateId!]?.includes(shape)) easy += s.end - s.start;
    }
    out.push({ capo, easyShare: easy / total });
  }
  // При равенстве — меньший каподастр.
  return out.sort((a, b) => b.easyShare - a.easyShare - (a.capo - b.capo) * 0.001);
}

/** Название формы аккорда при каподастре (что зажимать). */
export function shapeName(seg: ChordSegment, capo: number): string {
  if (seg.rootPc == null || !seg.templateId) return seg.symbol;
  const t = CHORD_TEMPLATES.find((x) => x.id === seg.templateId)!;
  return chordName(mod12(seg.rootPc - capo), t).symbol;
}
