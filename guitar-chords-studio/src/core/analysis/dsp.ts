// Обработка звука для распознавания аккордов: БПФ, спектр по полутонам, поиск звучащих нот
// с учётом обертонов, хромаграмма (какие из 12 нот звучат) и отдельно — бас.
//
// Почему не просто «энергия по нотам»: у струны кроме основного тона есть обертоны —
// октава, квинта через октаву, большая терция через две октавы (5-я гармоника) и т. д.
// Если их не учитывать, нота G «рисует» в спектре ещё D и B, и G5 выглядит как Gmaj7.

export const SEMI_LO = 24; // C1
export const SEMI_HI = 107; // B7
export const SEMI_COUNT = SEMI_HI - SEMI_LO + 1;

/** Быстрое преобразование Фурье (радикс-2, на месте). Длина — степень двойки. */
export function fft(re: Float64Array, im: Float64Array) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len;
    const wr = Math.cos(ang);
    const wi = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let cr = 1;
      let ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const a = i + k;
        const b = a + len / 2;
        const tr = re[b] * cr - im[b] * ci;
        const ti = re[b] * ci + im[b] * cr;
        re[b] = re[a] - tr;
        im[b] = im[a] - ti;
        re[a] += tr;
        im[a] += ti;
        const t = cr * wr - ci * wi;
        ci = cr * wi + ci * wr;
        cr = t;
      }
    }
  }
}

export interface ChromaFrame {
  /** Энергия 12 нот (C..B) в диапазоне аккомпанемента. */
  chroma: Float32Array;
  /** Энергия 12 нот в басу (E1–G3). */
  bass: Float32Array;
  /** Общая громкость кадра (RMS). */
  rms: number;
}

export class SpectrumAnalyzer {
  readonly size: number;
  private window: Float64Array;
  private re: Float64Array;
  private im: Float64Array;
  /** Для каждого бина: индекс полутона и вес (0 — бин не используется). */
  private binSemi: Int16Array;
  private binWeight: Float32Array;

  /**
   * tuning — строй записи в полутонах относительно A = 440 Гц (например, +0,4 — выше на 40 центов):
   * сетка нот сдвигается, чтобы расстроенная запись попадала точно в свои ноты.
   */
  constructor(
    size: number,
    readonly sampleRate: number,
    readonly tuning = 0,
  ) {
    this.size = size;
    this.window = new Float64Array(size);
    for (let i = 0; i < size; i++) this.window[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (size - 1));
    this.re = new Float64Array(size);
    this.im = new Float64Array(size);
    const bins = size / 2;
    this.binSemi = new Int16Array(bins).fill(-1);
    this.binWeight = new Float32Array(bins);
    for (let k = 1; k < bins; k++) {
      const f = (k * sampleRate) / size;
      const midi = 69 + 12 * Math.log2(f / 440) - tuning;
      const semi = Math.round(midi);
      if (semi < SEMI_LO || semi > SEMI_HI) continue;
      // Ближе к центру ноты — больше вес; бины «между нотами» почти не учитываются.
      const dist = Math.abs(midi - semi);
      this.binSemi[k] = semi - SEMI_LO;
      this.binWeight[k] = Math.max(0, 1 - dist * 2.2);
    }
  }

  /** Спектр по полутонам (MIDI SEMI_LO..SEMI_HI) для кадра длиной size. */
  semitones(frame: ArrayLike<number>, offset = 0): { semi: Float32Array; rms: number } {
    const { re, im, window, size } = this;
    let sum = 0;
    for (let i = 0; i < size; i++) {
      const v = frame[offset + i] ?? 0;
      sum += v * v;
      re[i] = v * window[i];
      im[i] = 0;
    }
    fft(re, im);
    const semi = new Float32Array(SEMI_COUNT);
    for (let k = 1; k < size / 2; k++) {
      const s = this.binSemi[k];
      if (s < 0) continue;
      const mag = Math.hypot(re[k], im[k]);
      // Берём максимум по бинам ноты: пик важнее «размазанной» энергии между нотами.
      const v = mag * this.binWeight[k];
      if (v > semi[s]) semi[s] = v;
    }
    return { semi, rms: Math.sqrt(sum / size) };
  }

  /**
   * Вклад кадра в оценку строя: по пикам спектра (с уточнением положения пика) — насколько они
   * отклоняются от ближайших нот. Возвращает вектор на круге отклонений; сумма по кадрам → строй.
   */
  tuningVector(frame: ArrayLike<number>, offset = 0): [number, number] {
    const { re, im, window, size, sampleRate } = this;
    for (let i = 0; i < size; i++) {
      re[i] = (frame[offset + i] ?? 0) * window[i];
      im[i] = 0;
    }
    fft(re, im);
    const bins = size / 2;
    const mag = new Float32Array(bins);
    for (let k = 1; k < bins; k++) mag[k] = Math.hypot(re[k], im[k]);
    const lo = Math.ceil((180 * size) / sampleRate);
    const hi = Math.min(bins - 2, Math.floor((2000 * size) / sampleRate));
    let peak = 0;
    for (let k = lo; k <= hi; k++) peak = Math.max(peak, mag[k]);
    let x = 0;
    let y = 0;
    for (let k = lo; k <= hi; k++) {
      const m = mag[k];
      if (m < peak * 0.1 || m < mag[k - 1] || m < mag[k + 1]) continue;
      // Параболическое уточнение пика (по логарифму амплитуды).
      const a = Math.log(mag[k - 1] + 1e-12);
      const b = Math.log(m + 1e-12);
      const c = Math.log(mag[k + 1] + 1e-12);
      const den = a - 2 * b + c;
      const kk = den !== 0 ? k + (0.5 * (a - c)) / den : k;
      const midi = 69 + 12 * Math.log2((kk * sampleRate) / size / 440);
      const dev = midi - Math.round(midi);
      const w = m * m;
      x += w * Math.cos(2 * Math.PI * dev);
      y += w * Math.sin(2 * Math.PI * dev);
    }
    return [x, y];
  }

  frame(samples: ArrayLike<number>, offset = 0): ChromaFrame {
    const { semi, rms } = this.semitones(samples, offset);
    const { chroma } = chromaFromNotes(detectNotes(semi));
    return { chroma, bass: bassSalience(semi), rms };
  }
}

// Обертоны струны: сдвиг от основного тона в полутонах (гармоники 1..8) и вес в «силе» ноты.
const PARTIALS: [number, number][] = [
  [0, 1],
  [12, 0.8],
  [19, 0.65],
  [24, 0.55],
  [28, 0.5],
  [31, 0.45],
  [34, 0.4],
  [36, 0.35],
];

export interface DetectedNote {
  midi: number;
  strength: number;
}

/**
 * Поиск нескольких одновременно звучащих нот (итеративная оценка с вычитанием, по Клапури):
 * находим ноту, у которой в спектре сильнее всего представлены её обертоны, запоминаем её,
 * убираем её обертоны из спектра и повторяем. Так обертон струны G (нота D) не принимается
 * за отдельную ноту.
 */
/**
 * lowerMin — насколько сильным (доля от найденной) должен быть основной тон более низкой ноты,
 * чтобы найденная считалась её обертоном. Для обычного спектра хватает 5 %; для прироста
 * («что добавилось после щипка») нужно больше: там слабый случайный прирост на басовой струне
 * (биения звенящих струн) иначе «съедает» новую ноту — ми 1-й струны становилась ля 5-й.
 */
export function detectNotes(semi: Float32Array, maxNotes = 8, maxMidi = 69, lowerMin = 0.05): DetectedNote[] {
  const s = Float32Array.from(semi);
  const notes: DetectedNote[] = [];
  let first = 0;
  const salience = (i: number) => {
    let sal = 0;
    for (const [off, w] of PARTIALS) if (i + off < s.length) sal += w * s[i + off];
    return sal;
  };
  for (let n = 0; n < maxNotes; n++) {
    let best = -1;
    let bestSal = 0;
    for (let i = 0; i < s.length; i++) {
      const midi = SEMI_LO + i;
      // Ноты гитарного аккорда почти всегда ниже A4; выше в основном обертоны.
      if (midi < 35 || midi > maxMidi) continue;
      // Основной тон должен реально звучать, иначе это «фантом» из обертонов.
      if (s[i] <= 0) continue;
      const sal = salience(i);
      if (sal > bestSal) {
        bestSal = sal;
        best = i;
      }
    }
    // Не обертон ли это более низкой звучащей ноты? Тогда сначала берём её.
    for (let changed = true; changed && best >= 0;) {
      changed = false;
      // Только сдвиги, меняющие название ноты (3-я и 5-я гармоники): октавы на аккорд не влияют,
      // а «достраивание» несуществующей низкой ноты стирало бы терцию.
      for (const off of [19, 28]) {
        const q = best - off;
        if (q < 0 || SEMI_LO + q < 35) continue;
        if (s[q] >= s[best] * lowerMin && salience(q) >= bestSal * 0.35) {
          best = q;
          bestSal = salience(q);
          changed = true;
          break;
        }
      }
    }
    if (best < 0) break;
    if (n === 0) first = bestSal;
    else if (bestSal < first * 0.1) break;
    notes.push({ midi: SEMI_LO + best, strength: bestSal });
    s[best] = 0;
    for (const [off] of PARTIALS.slice(1)) if (best + off < s.length) s[best + off] *= 0.03;
  }
  return notes;
}

/**
 * Бас по низкому регистру: для каждой ноты B1..E3 суммируем её обертоны (основной тон
 * не обязателен — у низких струн в записи он часто почти не слышен, но ухо «достраивает»
 * его по гармоникам). Возвращает 12 чисел — насколько вероятна каждая нота в басу.
 */
export function bassSalience(semi: Float32Array): Float32Array {
  const bass = new Float32Array(12);
  const cand: { midi: number; sal: number }[] = [];
  for (let midi = 35; midi <= 52; midi++) {
    const i = midi - SEMI_LO;
    let sal = 0;
    for (const [off, w] of PARTIALS.slice(0, 6)) if (i + off < semi.length) sal += w * semi[i + off];
    cand.push({ midi, sal });
  }
  const max = Math.max(...cand.map((c) => c.sal));
  if (max <= 0) return bass;
  // Кандидат ниже по высоте при почти равной силе предпочтительнее: октава/квинта выше —
  // это его же обертоны.
  for (const c of cand) {
    const v = c.sal / max;
    bass[c.midi % 12] = Math.max(bass[c.midi % 12], v * (1 + (52 - c.midi) / 60));
  }
  return bass;
}

/** Хромаграмма и басовая хромаграмма по найденным нотам. */
export function chromaFromNotes(notes: DetectedNote[]): { chroma: Float32Array; bass: Float32Array } {
  const chroma = new Float32Array(12);
  const bass = new Float32Array(12);
  if (!notes.length) return { chroma, bass };
  const max = Math.max(...notes.map((n) => n.strength));
  const low = Math.min(...notes.filter((n) => n.strength >= max * 0.25).map((n) => n.midi));
  for (const n of notes) {
    // Найденная нота важна сама по себе: тихая терция решает, мажор это или минор.
    const v = 0.5 + 0.5 * Math.sqrt(n.strength / max);
    chroma[n.midi % 12] += v;
    // Бас — самая низкая уверенная нота и соседние снизу вверх с убывающим весом.
    if (n.midi <= 57) bass[n.midi % 12] += v * (n.midi === low ? 1 : 0.35) * (1 + (57 - n.midi) / 24);
  }
  return { chroma, bass };
}

/** Строй по сумме векторов tuningVector: смещение в полутонах в диапазоне −0,5…+0,5. */
export function tuningFromVector(x: number, y: number): number {
  if (!x && !y) return 0;
  return Math.atan2(y, x) / (2 * Math.PI);
}
