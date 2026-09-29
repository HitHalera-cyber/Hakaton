// Распознавание аккорда по хромаграмме: сравнение с шаблонами всех аккордов от всех 12 тоник.
// Сходство — косинус между «профилем» звука и профилем аккорда (терция и тоника весят больше,
// квинта меньше — она часто теряется или совпадает с обертоном). Бас даёт бонус тонике и
// позволяет распознать обращение (C/E).

import { CHORD_TEMPLATES, parseDegree, type ChordTemplate } from '../music/chords';
import { chordName } from '../music/chordParse';
import { mod12 } from '../music/notes';

/** Словарь для живой игры: всё, что часто играют на гитаре. */
export const LIVE_VOCAB = ['maj', 'min', '7', 'maj7', 'm7', 'sus2', 'sus4', 'dim', 'aug', '6', 'm6', 'add9', 'm7b5', 'dim7', '5'];
/** Словари для разбора песен: чем меньше вариантов, тем меньше ошибок. */
export const SONG_VOCAB = {
  simple: ['maj', 'min'],
  sevenths: ['maj', 'min', '7', 'm7', 'maj7'],
} as const;

const DEGREE_WEIGHT = (d: string) => (d === '1' ? 1 : d === '3' || d === 'b3' ? 1 : d.endsWith('5') ? 0.75 : d.endsWith('7') ? 0.9 : 0.8);

export interface ChordModel {
  rootPc: number;
  template: ChordTemplate;
  vec: Float32Array;
  size: number;
}

export function buildModels(ids: readonly string[]): ChordModel[] {
  const out: ChordModel[] = [];
  for (const id of ids) {
    const t = CHORD_TEMPLATES.find((x) => x.id === id);
    if (!t) continue;
    for (let root = 0; root < 12; root++) {
      const vec = new Float32Array(12);
      for (const d of t.degrees) vec[mod12(root + parseDegree(d).semis)] = DEGREE_WEIGHT(d);
      let norm = 0;
      for (const v of vec) norm += v * v;
      norm = Math.sqrt(norm);
      for (let i = 0; i < 12; i++) vec[i] /= norm;
      out.push({ rootPc: root, template: t, vec, size: t.degrees.length });
    }
  }
  return out;
}

/** Оценки всех моделей для кадра (выше — лучше, примерно 0..1). */
export function scoreModels(chroma: ArrayLike<number>, bass: ArrayLike<number> | null, models: ChordModel[]): Float32Array {
  let norm = 0;
  for (let i = 0; i < 12; i++) norm += chroma[i] * chroma[i];
  norm = Math.sqrt(norm) || 1;
  let bassMax = 0;
  if (bass) for (let i = 0; i < 12; i++) bassMax = Math.max(bassMax, bass[i]);
  const scores = new Float32Array(models.length);
  models.forEach((m, k) => {
    let dot = 0;
    for (let i = 0; i < 12; i++) dot += (chroma[i] / norm) * m.vec[i];
    let s = dot;
    if (bass && bassMax > 0) s += 0.1 * (bass[m.rootPc] / bassMax);
    s -= 0.012 * Math.max(0, m.size - 3); // при равенстве — более простой аккорд
    if (m.template.id === '5') s -= 0.03;
    scores[k] = s;
  });
  return scores;
}

export interface RecognizedChord {
  rootPc: number;
  templateId: string;
  bassPc?: number;
  symbol: string;
  nameRu: string;
  /** Уверенность 0..1. */
  confidence: number;
}

export interface Recognition {
  best: RecognizedChord | null;
  alternatives: RecognizedChord[];
}

/** Распознать аккорд по усреднённой хромаграмме звучащего аккорда. */
export function recognizeChord(chroma: ArrayLike<number>, bass: ArrayLike<number> | null, models: ChordModel[]): Recognition {
  let energy = 0;
  for (let i = 0; i < 12; i++) energy += chroma[i];
  if (energy <= 0) return { best: null, alternatives: [] };

  const scores = scoreModels(chroma, bass, models);
  const order = [...scores.keys()].sort((a, b) => scores[b] - scores[a]);
  // Уверенность — «мягкий максимум» по лучшим вариантам.
  const top = order.slice(0, 6);
  const exps = top.map((k) => Math.exp((scores[k] - scores[top[0]]) / 0.025));
  const total = exps.reduce((a, b) => a + b, 0);

  // Бас: явно самая сильная низкая нота, входящая в аккорд, — обращение.
  let bassPc: number | undefined;
  if (bass) {
    const sorted = [...Array(12).keys()].sort((a, b) => bass[b] - bass[a]);
    if (bass[sorted[0]] > 0 && bass[sorted[1]] < bass[sorted[0]] * 0.75) bassPc = sorted[0];
  }

  const seen = new Set<string>();
  const list: RecognizedChord[] = [];
  top.forEach((k, i) => {
    const m = models[k];
    const inChord = bassPc != null && m.vec[bassPc] > 0 && bassPc !== m.rootPc;
    const name = chordName(m.rootPc, m.template, inChord ? bassPc : undefined);
    if (seen.has(name.symbol)) return;
    seen.add(name.symbol);
    list.push({
      rootPc: m.rootPc,
      templateId: m.template.id,
      bassPc: inChord ? bassPc : undefined,
      symbol: name.symbol,
      nameRu: name.nameRu,
      confidence: exps[i] / total,
    });
  });
  return { best: list[0] ?? null, alternatives: list.slice(1, 4) };
}
