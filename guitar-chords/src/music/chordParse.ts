// Разбор буквенного обозначения аккорда: «Cmaj7», «Dm/F», «F#m7b5», «Bb», «Asus», «G°7»…

import { CHORD_TEMPLATES, parseDegree, type ChordTemplate } from './chords';
import { LETTER_PC, mod12, spelledName, spelledRu, type Spelled } from './notes';

export interface ParsedChord {
  root: Spelled;
  rootPc: number;
  template: ChordTemplate;
  bass?: Spelled;
  bassPc?: number;
  symbol: string;
  nameRu: string;
}

// Синонимы суффиксов → суффикс шаблона.
const ALIASES: Record<string, string> = {
  '': '',
  maj: '',
  M: '',
  major: '',
  min: 'm',
  minor: 'm',
  '-': 'm',
  mi: 'm',
  M7: 'maj7',
  Maj7: 'maj7',
  ma7: 'maj7',
  'Δ': 'maj7',
  'Δ7': 'maj7',
  j7: 'maj7',
  'maj9': 'maj9',
  M9: 'maj9',
  'min7': 'm7',
  '-7': 'm7',
  mi7: 'm7',
  'm7-5': 'm7b5',
  'm7(b5)': 'm7b5',
  'ø': 'm7b5',
  'ø7': 'm7b5',
  'min7b5': 'm7b5',
  '°': 'dim',
  o: 'dim',
  '°7': 'dim7',
  o7: 'dim7',
  '+': 'aug',
  '#5': 'aug',
  '+7': '7#5',
  aug7: '7#5',
  'maj7+5': 'maj7#5',
  sus: 'sus4',
  '7sus': '7sus4',
  add2: 'add9',
  '2': 'sus2',
  madd2: 'madd9',
  '69': '6/9',
  '6add9': '6/9',
  dom7: '7',
  mmaj7: 'm(maj7)',
  mM7: 'm(maj7)',
  'm/maj7': 'm(maj7)',
  'mMaj7': 'm(maj7)',
  'min6': 'm6',
  '-6': 'm6',
  'min9': 'm9',
  '-9': 'm9',
  'min11': 'm11',
  '7(b9)': '7b9',
  '7(#9)': '7#9',
  '5': '5',
  power: '5',
};

function parseNote(s: string): { spelled: Spelled; rest: string } | null {
  const m = /^([A-Ga-g])(##|#|bb|b|♯|♭)?(.*)$/.exec(s.trim());
  if (!m) return null;
  const letter = 'CDEFGAB'.indexOf(m[1].toUpperCase());
  const accRaw = (m[2] ?? '').replace('♯', '#').replace('♭', 'b');
  const acc = accRaw === '#' ? 1 : accRaw === '##' ? 2 : accRaw === 'b' ? -1 : accRaw === 'bb' ? -2 : 0;
  return { spelled: { letter, acc }, rest: m[3] };
}

/** Разобрать обозначение. Возвращает null, если не удалось. */
export function parseChordSymbol(input: string): ParsedChord | null {
  const text = input.trim().replace(/\s+/g, '').replace(/♯/g, '#').replace(/♭/g, 'b');
  if (!text) return null;
  const head = parseNote(text);
  if (!head) return null;

  let rest = head.rest;
  let bass: Spelled | undefined;
  const slash = rest.lastIndexOf('/');
  if (slash >= 0 && !/^(6\/9)$/.test(rest)) {
    const b = parseNote(rest.slice(slash + 1));
    if (b && b.rest === '') {
      bass = b.spelled;
      rest = rest.slice(0, slash);
    }
  }

  const suffix = ALIASES[rest] ?? rest;
  const template = CHORD_TEMPLATES.find((t) => t.suffix === suffix);
  if (!template) return null;

  const root = head.spelled;
  const rootPc = mod12(LETTER_PC[root.letter] + root.acc);
  const bassPc = bass ? mod12(LETTER_PC[bass.letter] + bass.acc) : undefined;
  const symbol = spelledName(root) + template.suffix + (bass && bassPc !== rootPc ? '/' + spelledName(bass) : '');
  const nameRu = `${spelledRu(root)} ${template.ru}` + (bass && bassPc !== rootPc ? `, бас ${spelledRu(bass)}` : '');
  return { root, rootPc, template, bass, bassPc: bassPc === rootPc ? undefined : bassPc, symbol, nameRu };
}

/** Высотные классы аккорда: обязательные и пропускаемые. */
export function chordPitchClasses(rootPc: number, t: ChordTemplate) {
  const omit = new Set(t.omit ?? []);
  return t.degrees.map((d) => ({ degree: d, pc: mod12(rootPc + parseDegree(d).semis), optional: omit.has(d) }));
}
