// Проверка аппликатуры по струнам: аккорд зажат, струны щиплются по одной от 6-й к 1-й (и
// заглушённые тоже). Каждая струна оценивается отдельно: та ли нота, чисто ли звучит, не звенит ли
// струна, которая должна молчать. Так надёжнее, чем по одному удару, где ноты струн перекрываются.

import type { Pluck } from './stringPick';

export interface ExpectedString {
  /** Номер струны (0 — басовая). */
  string: number;
  /** Нота, которая должна звучать; null — струна должна молчать. */
  midi: number | null;
  /** Нота открытой струны с учётом каподастра. */
  openMidi: number;
}

export type StringStatus = 'ok' | 'weak' | 'quiet' | 'missing' | 'open' | 'wrong' | 'silent' | 'ringing' | 'skipped';

export interface StringVerdict {
  string: number;
  midi: number | null;
  status: StringStatus;
  /** Что услышано (нота), если отличается от нужной. */
  heard?: number;
  /** Чистота звука 0..1. */
  clarity: number;
}

/** Ниже такой чистоты нота звучит с призвуком: дребезг, палец касается струны. */
const CLEAN = 0.55;

/** Оценка одной струны по её щипку (null — щипка не было). */
export function judgeString(e: ExpectedString, p: Pluck | null): StringVerdict {
  const base = { string: e.string, midi: e.midi, clarity: p?.clarity ?? 0 };
  if (!p) return { ...base, status: e.midi == null ? 'silent' : 'skipped' };
  if (e.midi == null) {
    // Должна молчать: глухой стук — правильно, звонкая нота — струна не заглушена.
    return p.midi == null ? { ...base, status: 'silent' } : { ...base, status: 'ringing', heard: p.midi };
  }
  if (p.midi == null) return { ...base, status: 'missing' };
  if (p.midi === e.midi) return { ...base, status: p.clarity < CLEAN ? 'weak' : 'ok' };
  // Октава выше/ниже на той же струне не бывает — это ошибка распознавания; засчитываем, но с пометкой.
  if (Math.abs(p.midi - e.midi) === 12) return { ...base, status: p.clarity < CLEAN ? 'weak' : 'ok' };
  if (p.midi === e.openMidi) return { ...base, status: 'open', heard: p.midi };
  return { ...base, status: 'wrong', heard: p.midi };
}

/**
 * На какую струну пришёлся щипок: обычно на следующую по порядку. Но если щипок совпал с нотой
 * одной из следующих струн, а не текущей, — значит, программа пропустила щипок (или вы пропустили
 * струну), и мы перескакиваем.
 */
export function alignPluck(expected: ExpectedString[], cursor: number, p: Pluck): number {
  if (cursor >= expected.length) return cursor;
  const cur = expected[cursor];
  // Щипок подходит текущей струне (в том числе ошибки на ней: открытая нота, звон заглушённой).
  if (p.midi == null || p.midi === cur.midi || p.midi === cur.openMidi) return cursor;
  if (cur.midi != null && Math.abs(p.midi - cur.midi) <= 2) return cursor;
  // Точно совпал с одной из двух следующих струн — значит, щипок текущей пропущен.
  for (let s = cursor + 1; s < Math.min(expected.length, cursor + 3); s++) if (expected[s].midi === p.midi) return s;
  return cursor;
}

/** Итог: сколько струн в порядке и тихие струны (заметно тише остальных — их приглушает палец). */
export function summarize(verdicts: StringVerdict[], plucks: (Pluck | null)[]): { good: number; total: number } {
  const energies = plucks.map((p, i) => (verdicts[i].status === 'ok' && p?.energy ? p.energy : 0)).filter((x) => x > 0);
  const med = energies.length ? [...energies].sort((a, b) => a - b)[energies.length >> 1] : 0;
  verdicts.forEach((v, i) => {
    const en = plucks[i]?.energy ?? 0;
    if (v.status === 'ok' && med > 0 && en < med * 0.15) v.status = 'quiet';
  });
  const good = verdicts.filter((v) => v.status === 'ok' || v.status === 'silent').length;
  return { good, total: verdicts.length };
}
