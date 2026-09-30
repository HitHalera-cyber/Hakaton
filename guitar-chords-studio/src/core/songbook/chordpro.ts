// Формат песни ChordPro: аккорд в квадратных скобках стоит перед слогом, на котором он звучит.
//   {Куплет}
//   [Am]Вот новый [F]поворот
// Здесь: разбор в строки для показа, импорт «строка аккордов над строкой текста», транспонирование,
// и заготовка песни из разбора аудио (аккорды по тактам).

import { chordName, parseChordSymbol } from '../music/chordParse';
import { mod12 } from '../music/notes';

export interface SongPart {
  chord?: string;
  text: string;
}

export type SongLine = { kind: 'section'; title: string } | { kind: 'empty' } | { kind: 'lyrics'; parts: SongPart[] };

/** Разбор текста песни на строки: заголовки разделов, пустые строки, строки с аккордами. */
export function parseChordPro(body: string): SongLine[] {
  return body.split(/\r?\n/).map((raw): SongLine => {
    const line = raw.replace(/\s+$/, '');
    const section = /^\{\s*(?:c:|comment:|title:)?\s*([^}]*)\}$/i.exec(line.trim());
    if (section) return { kind: 'section', title: section[1].trim() };
    if (!line.trim()) return { kind: 'empty' };
    const parts: SongPart[] = [];
    const re = /\[([^\]]+)\]/g;
    let last = 0;
    let chord: string | undefined;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line))) {
      if (m.index > last || chord) parts.push({ chord, text: line.slice(last, m.index) });
      chord = m[1].trim();
      last = m.index + m[0].length;
    }
    parts.push({ chord, text: line.slice(last) });
    return { kind: 'lyrics', parts: parts.filter((p, i) => p.chord || p.text || i === 0) };
  });
}

/** Все аккорды песни по порядку первого появления. */
export function songChords(body: string): string[] {
  const seen = new Set<string>();
  for (const m of body.matchAll(/\[([^\]]+)\]/g)) seen.add(m[1].trim());
  return [...seen].filter((c) => parseChordSymbol(c));
}

/** Сдвинуть аккорд на k полутонов. Непонятные обозначения остаются как есть. */
export function transposeSymbol(symbol: string, k: number): string {
  if (!k) return symbol;
  const p = parseChordSymbol(symbol);
  if (!p) return symbol;
  return chordName(mod12(p.rootPc + k), p.template, p.bassPc != null ? mod12(p.bassPc + k) : undefined).symbol;
}

export function transposeBody(body: string, k: number): string {
  return k ? body.replace(/\[([^\]]+)\]/g, (_, c: string) => `[${transposeSymbol(c.trim(), k)}]`) : body;
}

/** Строка состоит только из аккордов (и пробелов, тактовых черт): «Am   F   C  G». */
function isChordLine(line: string): boolean {
  const tokens = line
    .trim()
    .split(/\s+/)
    .filter((t) => t && t !== '|' && t !== '-');
  return tokens.length > 0 && tokens.every((t) => parseChordSymbol(t) != null);
}

/**
 * Импорт песни с сайта: строка аккордов над строкой текста превращается в ChordPro —
 * каждый аккорд встаёт в текст по своей позиции над ним. Уже размеченный текст не меняется.
 */
export function importChordsOverText(text: string): string {
  const lines = text.replace(/\t/g, '    ').split(/\r?\n/);
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!isChordLine(line)) {
      out.push(line);
      continue;
    }
    const chords = [...line.matchAll(/\S+/g)].filter((m) => m[0] !== '|' && m[0] !== '-').map((m) => ({ pos: m.index!, chord: m[0] }));
    const next = lines[i + 1];
    if (next != null && next.trim() && !isChordLine(next) && !/^\s*[{[]/.test(next)) {
      let lyric = next.padEnd(Math.max(next.length, ...chords.map((c) => c.pos)));
      for (const c of [...chords].reverse()) lyric = lyric.slice(0, c.pos) + `[${c.chord}]` + lyric.slice(c.pos);
      out.push(lyric.replace(/\s+$/, ''));
      i++;
    } else out.push(chords.map((c) => `[${c.chord}]`).join(' '));
  }
  return out.join('\n');
}

/** Заготовка песни из разбора аудио: аккорды по тактам, по 4 такта в строке. */
export function chordsToBars(chords: { symbol: string; beats: number }[], meter = 4, barsPerLine = 4): string {
  const bars: string[][] = [];
  let beat = 0;
  for (const c of chords) {
    const bar = Math.floor(beat / meter);
    (bars[bar] ??= []).push(c.symbol);
    beat += Math.max(1, Math.round(c.beats));
  }
  // Такты без новой смены — продолжение предыдущего аккорда («%»).
  const total = Math.max(bars.length, Math.ceil(beat / meter));
  const cells = Array.from({ length: total }, (_, i) => (bars[i]?.length ? bars[i].map((c) => `[${c}]`).join(' ') : '%'));
  const lines: string[] = [];
  for (let i = 0; i < cells.length; i += barsPerLine) lines.push('| ' + cells.slice(i, i + barsPerLine).join(' | ') + ' |');
  return lines.join('\n');
}
