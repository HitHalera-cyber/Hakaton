// Определение аккорда по набору звучащих нот.
//
// Алгоритм: каждая нота набора по очереди пробуется как тоника; интервалы остальных нот
// от неё сравниваются с шаблонами аккордов. Совпадения оцениваются баллами:
//   + точное совпадение (все ноты объяснены шаблоном, все обязательные ступени есть),
//   + тоника в басу (иначе — обращение, записывается через «/», напр. C/E),
//   − пропущенные необязательные ступени (обычно квинта),
//   + «популярность» аккорда (чтобы при равенстве Am7 побеждал C6/A и т.п.).
// Неточные совпадения (одна лишняя или одна недостающая нота) — это «ближайшие варианты».
// Работа ведётся по высотным классам, поэтому любая аппликатура и любое
// обращение одного аккорда распознаются одинаково.

import { INTERVAL_RU, defaultSpelling, mod12, pcName, spellInterval, spelledName, spelledRu, type Spelled } from './notes';

export type ChordKind = 'triad' | 'seventh' | 'other';

export interface ChordTemplate {
  id: string;
  /** Суффикс буквенного обозначения: '', 'm', '7', 'maj7'... */
  suffix: string;
  /** Русское название качества: «мажор», «минорный септаккорд»... */
  ru: string;
  /** Ступени от тоники: '1', 'b3', '5', 'b7', '9'... */
  degrees: string[];
  /** Ступени, которые можно пропустить без смены названия. */
  omit?: string[];
  kind: ChordKind;
  /** Популярность (0..10) — разрешает неоднозначности. */
  weight: number;
}

export const CHORD_TEMPLATES: ChordTemplate[] = [
  { id: 'maj', suffix: '', ru: 'мажор', degrees: ['1', '3', '5'], kind: 'triad', weight: 10 },
  { id: 'min', suffix: 'm', ru: 'минор', degrees: ['1', 'b3', '5'], kind: 'triad', weight: 10 },
  { id: 'dim', suffix: 'dim', ru: 'уменьшённое трезвучие', degrees: ['1', 'b3', 'b5'], kind: 'triad', weight: 6 },
  { id: 'aug', suffix: 'aug', ru: 'увеличенное трезвучие', degrees: ['1', '3', '#5'], kind: 'triad', weight: 5 },
  { id: 'sus2', suffix: 'sus2', ru: 'с задержанием секунды (sus2)', degrees: ['1', '2', '5'], kind: 'other', weight: 6 },
  { id: 'sus4', suffix: 'sus4', ru: 'с задержанием кварты (sus4)', degrees: ['1', '4', '5'], kind: 'other', weight: 7 },
  { id: '5', suffix: '5', ru: 'квинтаккорд (пауэр-аккорд)', degrees: ['1', '5'], kind: 'other', weight: 8 },
  { id: '6', suffix: '6', ru: 'мажор с секстой', degrees: ['1', '3', '5', '6'], omit: ['5'], kind: 'other', weight: 6 },
  { id: 'm6', suffix: 'm6', ru: 'минор с секстой', degrees: ['1', 'b3', '5', '6'], omit: ['5'], kind: 'other', weight: 5 },
  { id: '7', suffix: '7', ru: 'мажорный септаккорд', degrees: ['1', '3', '5', 'b7'], omit: ['5'], kind: 'seventh', weight: 9 },
  { id: 'maj7', suffix: 'maj7', ru: 'большой мажорный септаккорд', degrees: ['1', '3', '5', '7'], omit: ['5'], kind: 'seventh', weight: 8 },
  { id: 'm7', suffix: 'm7', ru: 'минорный септаккорд', degrees: ['1', 'b3', '5', 'b7'], omit: ['5'], kind: 'seventh', weight: 9 },
  {
    id: 'mMaj7',
    suffix: 'm(maj7)',
    ru: 'минорный септаккорд с большой септимой',
    degrees: ['1', 'b3', '5', '7'],
    omit: ['5'],
    kind: 'seventh',
    weight: 4,
  },
  { id: 'm7b5', suffix: 'm7b5', ru: 'полууменьшённый септаккорд', degrees: ['1', 'b3', 'b5', 'b7'], kind: 'seventh', weight: 6 },
  { id: 'dim7', suffix: 'dim7', ru: 'уменьшённый септаккорд', degrees: ['1', 'b3', 'b5', 'bb7'], kind: 'seventh', weight: 6 },
  { id: '7#5', suffix: '7#5', ru: 'увеличенный септаккорд', degrees: ['1', '3', '#5', 'b7'], kind: 'seventh', weight: 3 },
  { id: '7b5', suffix: '7b5', ru: 'септаккорд с пониженной квинтой', degrees: ['1', '3', 'b5', 'b7'], kind: 'seventh', weight: 3 },
  { id: 'maj7#5', suffix: 'maj7#5', ru: 'большой увеличенный септаккорд', degrees: ['1', '3', '#5', '7'], kind: 'seventh', weight: 2 },
  {
    id: '7sus4',
    suffix: '7sus4',
    ru: 'септаккорд с задержанием кварты',
    degrees: ['1', '4', '5', 'b7'],
    omit: ['5'],
    kind: 'other',
    weight: 5,
  },
  {
    id: '7sus2',
    suffix: '7sus2',
    ru: 'септаккорд с задержанием секунды',
    degrees: ['1', '2', '5', 'b7'],
    omit: ['5'],
    kind: 'other',
    weight: 3,
  },
  { id: 'add9', suffix: 'add9', ru: 'мажор с добавленной ноной', degrees: ['1', '3', '5', '9'], omit: ['5'], kind: 'other', weight: 6 },
  { id: 'madd9', suffix: 'madd9', ru: 'минор с добавленной ноной', degrees: ['1', 'b3', '5', '9'], omit: ['5'], kind: 'other', weight: 5 },
  { id: 'add11', suffix: 'add11', ru: 'мажор с добавленной ундецимой', degrees: ['1', '3', '5', '11'], kind: 'other', weight: 3 },
  { id: '6/9', suffix: '6/9', ru: 'мажор с секстой и ноной', degrees: ['1', '3', '5', '6', '9'], omit: ['5'], kind: 'other', weight: 4 },
  { id: '9', suffix: '9', ru: 'мажорный нонаккорд', degrees: ['1', '3', '5', 'b7', '9'], omit: ['5'], kind: 'other', weight: 6 },
  {
    id: 'maj9',
    suffix: 'maj9',
    ru: 'большой мажорный нонаккорд',
    degrees: ['1', '3', '5', '7', '9'],
    omit: ['5'],
    kind: 'other',
    weight: 5,
  },
  { id: 'm9', suffix: 'm9', ru: 'минорный нонаккорд', degrees: ['1', 'b3', '5', 'b7', '9'], omit: ['5'], kind: 'other', weight: 5 },
  {
    id: '7b9',
    suffix: '7b9',
    ru: 'септаккорд с пониженной ноной',
    degrees: ['1', '3', '5', 'b7', 'b9'],
    omit: ['5'],
    kind: 'other',
    weight: 3,
  },
  {
    id: '7#9',
    suffix: '7#9',
    ru: 'септаккорд с повышенной ноной («аккорд Хендрикса»)',
    degrees: ['1', '3', '5', 'b7', '#9'],
    omit: ['5'],
    kind: 'other',
    weight: 4,
  },
  { id: '11', suffix: '11', ru: 'ундецимаккорд', degrees: ['1', '3', '5', 'b7', '9', '11'], omit: ['3', '5'], kind: 'other', weight: 3 },
  {
    id: 'm11',
    suffix: 'm11',
    ru: 'минорный ундецимаккорд',
    degrees: ['1', 'b3', '5', 'b7', '9', '11'],
    omit: ['5', '9'],
    kind: 'other',
    weight: 3,
  },
  {
    id: '13',
    suffix: '13',
    ru: 'терцдецимаккорд',
    degrees: ['1', '3', '5', 'b7', '9', '11', '13'],
    omit: ['5', '9', '11'],
    kind: 'other',
    weight: 3,
  },
  {
    id: 'maj13',
    suffix: 'maj13',
    ru: 'большой мажорный терцдецимаккорд',
    degrees: ['1', '3', '5', '7', '9', '13'],
    omit: ['5', '9'],
    kind: 'other',
    weight: 2,
  },
  {
    id: 'm13',
    suffix: 'm13',
    ru: 'минорный терцдецимаккорд',
    degrees: ['1', 'b3', '5', 'b7', '9', '13'],
    omit: ['5', '9'],
    kind: 'other',
    weight: 2,
  },
];

const NATURAL_SEMIS: Record<number, number> = { 1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 9: 14, 11: 17, 13: 21 };

export interface ParsedDegree {
  /** Сдвиг по буквам (0 — тоника, 2 — терция...). */
  letterSteps: number;
  /** Полутоны от тоники по модулю 12. */
  semis: number;
}

export function parseDegree(degree: string): ParsedDegree {
  const m = /^(bb|b|#)?(\d+)$/.exec(degree);
  if (!m) throw new Error(`Неизвестная ступень: ${degree}`);
  const num = Number(m[2]);
  const acc = m[1] === 'bb' ? -2 : m[1] === 'b' ? -1 : m[1] === '#' ? 1 : 0;
  return { letterSteps: (num - 1) % 7, semis: mod12(NATURAL_SEMIS[num] + acc) };
}

const OMITTABLE_IN_NEAR = new Set(['3', 'b3', '5']);

/** Ступень в родительном падеже: «без терции», «без квинты». */
const DEGREE_GENITIVE: Record<string, string> = {
  '1': 'примы',
  '2': 'секунды',
  '3': 'терции',
  b3: 'терции',
  '4': 'кварты',
  '5': 'квинты',
  b5: 'квинты',
  '#5': 'квинты',
  '6': 'сексты',
  '7': 'септимы',
  b7: 'септимы',
  bb7: 'септимы',
  '9': 'ноны',
  b9: 'ноны',
  '#9': 'ноны',
  '11': 'ундецимы',
  '13': 'терцдецимы',
};

export interface ChordMatch {
  template: ChordTemplate;
  root: Spelled;
  rootPc: number;
  bassPc: number;
  /** Буквенное обозначение, напр. «Am7», «C/E», «G(no3)». */
  symbol: string;
  /** Русская расшифровка, напр. «Ля минорный септаккорд». */
  nameRu: string;
  /** Пояснение про обращение / бас (если бас не тоника). */
  inversionRu?: string;
  /** Звуки аккорда в порядке ступеней. */
  notes: Spelled[];
  /** Ступени, соответствующие notes ('1', 'b3'...; '+' — лишняя нота). */
  degrees: string[];
  /** Высотный класс → ступень (для подсветки точек на грифе). */
  degreeByPc: Map<number, string>;
  exact: boolean;
  missing: string[];
  extras: number[];
  score: number;
}

export type DetectionKind = 'empty' | 'note' | 'interval' | 'chord' | 'unknown';

export interface DetectionResult {
  kind: DetectionKind;
  primary?: ChordMatch;
  alternatives: ChordMatch[];
  pitchClasses: number[];
  bassPc?: number;
  /** Ноты (по умолчанию в порядке от баса), напр. ['E', 'G', 'C']. */
  noteNames: string[];
  intervalRu?: string;
}

function rootSpelling(pc: number, template: ChordTemplate): Spelled {
  const minorLike = template.degrees.includes('b3') && !template.degrees.includes('3');
  if (minorLike && pc === 8) return { letter: 4, acc: 1 }; // G#m, а не Abm
  if (!minorLike && pc === 1) return { letter: 1, acc: -1 }; // Db, а не C# (C#-E#-G#)
  return defaultSpelling(pc);
}

function inversionName(template: ChordTemplate, bassDegree: string | undefined): string | undefined {
  if (!bassDegree) return undefined;
  const third = bassDegree === '3' || bassDegree === 'b3';
  const fifth = bassDegree === '5' || bassDegree === 'b5' || bassDegree === '#5';
  const seventh = bassDegree === '7' || bassDegree === 'b7' || bassDegree === 'bb7';
  if (template.kind === 'triad') {
    if (third) return 'секстаккорд (1-е обращение)';
    if (fifth) return 'квартсекстаккорд (2-е обращение)';
  }
  if (template.kind === 'seventh') {
    if (third) return 'квинтсекстаккорд (1-е обращение)';
    if (fifth) return 'терцквартаккорд (2-е обращение)';
    if (seventh) return 'секундаккорд (3-е обращение)';
  }
  return undefined;
}

function matchTemplate(pcs: number[], bassPc: number, rootPc: number, t: ChordTemplate): ChordMatch | null {
  const present = new Set(pcs.map((pc) => mod12(pc - rootPc)));
  const parsed = t.degrees.map((d) => ({ d, ...parseDegree(d) }));
  const templateSemis = new Set(parsed.map((p) => p.semis));
  const omit = new Set(t.omit ?? []);

  const missing: string[] = [];
  let omitted = 0;
  for (const p of parsed) {
    if (present.has(p.semis)) continue;
    if (omit.has(p.d)) omitted++;
    else missing.push(p.d);
  }
  const extras = [...present].filter((s) => !templateSemis.has(s)).map((s) => mod12(s + rootPc));
  if (missing.length + extras.length > 1) return null;
  // Пропустить можно только терцию или квинту: «C7 без септимы» — это уже не C7.
  if (missing.length && !OMITTABLE_IN_NEAR.has(missing[0])) return null;
  // Неточное совпадение имеет смысл, только если шаблон объясняет хотя бы 2 ноты.
  if (missing.length + extras.length === 1 && present.size - extras.length < 2) return null;

  const exact = missing.length === 0 && extras.length === 0;
  const score = 100 - 30 * missing.length - 25 * extras.length - 12 * omitted + (rootPc === bassPc ? 10 : 0) + t.weight;

  const root = rootSpelling(rootPc, t);
  const notes: Spelled[] = [];
  const degrees: string[] = [];
  const degreeByPc = new Map<number, string>();
  let bassSpelled: Spelled | undefined;
  let bassDegree: string | undefined;
  for (const p of parsed) {
    if (!present.has(p.semis)) continue;
    const s = spellInterval(root, p.letterSteps, p.semis);
    notes.push(s);
    degrees.push(p.d);
    degreeByPc.set(mod12(rootPc + p.semis), p.d);
    if (mod12(rootPc + p.semis) === bassPc) {
      bassSpelled = s;
      bassDegree = p.d;
    }
  }
  for (const pc of extras) {
    notes.push(defaultSpelling(pc));
    degrees.push('+');
    degreeByPc.set(pc, '+');
    if (pc === bassPc) bassSpelled = defaultSpelling(pc);
  }

  let symbol = spelledName(root) + t.suffix;
  let nameRu = `${spelledRu(root)} ${t.ru}`;
  if (missing.length) {
    symbol += `(no${missing[0].replace(/^[b#]+/, '')})`;
    nameRu += ` без ${DEGREE_GENITIVE[missing[0]] ?? missing[0]}`;
  }
  if (extras.length) {
    symbol += `(+${pcName(extras[0])})`;
    nameRu += ` с добавленной нотой ${spelledRu(defaultSpelling(extras[0]))}`;
  }

  let inversionRu: string | undefined;
  if (bassPc !== rootPc && bassSpelled) {
    symbol += '/' + spelledName(bassSpelled);
    const inv = exact ? inversionName(t, bassDegree) : undefined;
    inversionRu = `бас ${spelledRu(bassSpelled)}` + (inv ? ` — ${inv}` : '');
  }

  return {
    template: t,
    root,
    rootPc,
    bassPc,
    symbol,
    nameRu,
    inversionRu,
    notes,
    degrees,
    degreeByPc,
    exact,
    missing,
    extras,
    score,
  };
}

/** Определяет аккорд по списку MIDI-нот (порядок и дубли не важны). */
export function detectChord(midiNotes: number[]): DetectionResult {
  if (midiNotes.length === 0) return { kind: 'empty', alternatives: [], pitchClasses: [], noteNames: [] };

  const sorted = [...midiNotes].sort((a, b) => a - b);
  const bassPc = mod12(sorted[0]);
  const pcs: number[] = [];
  for (const m of sorted) if (!pcs.includes(mod12(m))) pcs.push(mod12(m));
  const noteNames = pcs.map(pcName);

  if (pcs.length === 1) {
    return { kind: 'note', alternatives: [], pitchClasses: pcs, bassPc, noteNames };
  }

  const matches: ChordMatch[] = [];
  for (const rootPc of pcs) {
    for (const t of CHORD_TEMPLATES) {
      const m = matchTemplate(pcs, bassPc, rootPc, t);
      if (m) matches.push(m);
    }
  }
  matches.sort((a, b) => Number(b.exact) - Number(a.exact) || b.score - a.score);
  const unique: ChordMatch[] = [];
  const seen = new Set<string>();
  for (const m of matches) {
    if (seen.has(m.symbol)) continue;
    seen.add(m.symbol);
    unique.push(m);
  }

  const best = unique[0];
  if (best?.exact) {
    return {
      // Другие трактовки — только точные (напр. C6 ↔ Am7/C), без «почти совпадений».
      kind: 'chord',
      primary: best,
      alternatives: unique
        .slice(1)
        .filter((m) => m.exact)
        .slice(0, 5),
      pitchClasses: pcs,
      bassPc,
      noteNames: best.notes.map(spelledName),
    };
  }

  if (pcs.length === 2) {
    const semis = mod12(pcs[1] - pcs[0]);
    return {
      kind: 'interval',
      alternatives: unique.slice(0, 5),
      pitchClasses: pcs,
      bassPc,
      noteNames,
      intervalRu: INTERVAL_RU[semis],
    };
  }

  return { kind: 'unknown', alternatives: unique.slice(0, 5), pitchClasses: pcs, bassPc, noteNames };
}
