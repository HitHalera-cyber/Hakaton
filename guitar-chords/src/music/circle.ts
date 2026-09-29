// Квартоквинтовый круг: по часовой стрелке — вверх на квинту (C → G → D …),
// против часовой — вверх на кварту (C → F → Bb …).
// Внешнее кольцо — мажорные аккорды, среднее — параллельные минорные (на малую терцию ниже),
// внутреннее — уменьшённые (VII ступень мажора, на полтона ниже тоники).

import { mod12 } from './notes';

/** Тоники мажорных тональностей по кругу, начиная с C сверху. */
export const CIRCLE_MAJOR = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5];

export const MAJOR_LABELS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'Db', 'Ab', 'Eb', 'Bb', 'F'];
export const MINOR_LABELS = ['Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m', 'Ebm', 'Bbm', 'Fm', 'Cm', 'Gm', 'Dm'];
export const DIM_LABELS = ['B°', 'F#°', 'C#°', 'G#°', 'D#°', 'A#°', 'F°', 'C°', 'G°', 'D°', 'A°', 'E°'];
/** Знаки при ключе: 1♯ у G, 1♭ у F. */
export const KEY_SIGNATURES = ['0', '1♯', '2♯', '3♯', '4♯', '5♯', '6♯/6♭', '5♭', '4♭', '3♭', '2♭', '1♭'];

export type Ring = 'major' | 'minor' | 'dim';

export interface CirclePos {
  ring: Ring;
  /** Позиция на круге 0..11 (0 — сверху, C / Am / B°). */
  index: number;
}

const MINOR_TYPES = new Set(['min', 'm7', 'm6', 'madd9', 'm9', 'm11', 'm13', 'mMaj7']);
const DIM_TYPES = new Set(['dim', 'm7b5', 'dim7']);

/** Где на круге аккорд с тоникой rootPc и типом templateId. */
export function circlePosition(rootPc: number, templateId: string): CirclePos {
  if (MINOR_TYPES.has(templateId)) return { ring: 'minor', index: CIRCLE_MAJOR.indexOf(mod12(rootPc + 3)) };
  if (DIM_TYPES.has(templateId)) return { ring: 'dim', index: CIRCLE_MAJOR.indexOf(mod12(rootPc + 1)) };
  // Мажорные и «нейтральные» аккорды (7, maj7, sus, 5, add9…) — на внешнем кольце.
  return { ring: 'major', index: CIRCLE_MAJOR.indexOf(mod12(rootPc)) };
}

/** Тоника и тип аккорда в ячейке круга. */
export function cellChord(pos: CirclePos): { rootPc: number; templateId: string } {
  const major = CIRCLE_MAJOR[mod12(pos.index)];
  if (pos.ring === 'minor') return { rootPc: mod12(major - 3), templateId: 'min' };
  if (pos.ring === 'dim') return { rootPc: mod12(major - 1), templateId: 'dim' };
  return { rootPc: major, templateId: 'maj' };
}

export interface CircleKey {
  /** Позиция мажорной тональности (параллельный минор — в той же позиции). */
  index: number;
  mode: 'major' | 'minor';
}

/** Входит ли ячейка в тональность: I–IV–V, ii–iii–vi и vii°. */
export function inKey(pos: CirclePos, key: CircleKey): boolean {
  const d = mod12(pos.index - key.index);
  if (pos.ring === 'dim') return d === 0;
  return d === 0 || d === 1 || d === 11;
}

/** Ступень аккорда в тональности римскими цифрами (или null, если аккорд чужой). */
export function romanInKey(pos: CirclePos, key: CircleKey): string | null {
  if (!inKey(pos, key)) return null;
  const d = mod12(pos.index - key.index);
  const off = d === 11 ? -1 : d;
  const major = key.mode === 'major';
  if (pos.ring === 'major') return major ? { [-1]: 'IV', 0: 'I', 1: 'V' }[off]! : { [-1]: 'VI', 0: 'III', 1: 'VII' }[off]!;
  if (pos.ring === 'minor') return major ? { [-1]: 'ii', 0: 'vi', 1: 'iii' }[off]! : { [-1]: 'iv', 0: 'i', 1: 'v' }[off]!;
  return major ? 'vii°' : 'ii°';
}

export const FUNCTION_RU: Record<string, string> = {
  I: 'тоника', i: 'тоника', IV: 'субдоминанта', iv: 'субдоминанта', V: 'доминанта', v: 'доминанта',
  ii: 'субдоминанта (II ступень)', 'ii°': 'II ступень', iii: 'III ступень', III: 'III ступень', vi: 'VI ступень', VI: 'VI ступень',
  VII: 'VII ступень', 'vii°': 'вводный аккорд (VII ступень)',
};

export function keyName(key: CircleKey): string {
  return key.mode === 'major' ? `${MAJOR_LABELS[key.index]} мажор` : `${MINOR_LABELS[key.index].replace('m', '')} минор`;
}

/**
 * Угадать тональность по недавно сыгранным аккордам (первый — самый свежий).
 * Тональность, в которую входит больше аккордов, побеждает; при равенстве — та, чья тоника звучала.
 */
export function guessKey(recent: CirclePos[]): CircleKey | null {
  if (recent.length === 0) return null;
  let best: { key: CircleKey; score: number } | null = null;
  for (let index = 0; index < 12; index++) {
    for (const mode of ['major', 'minor'] as const) {
      const key = { index, mode };
      let score = 0;
      recent.forEach((p, i) => {
        const w = Math.pow(0.85, i);
        if (inKey(p, key)) score += w;
        const tonicRing = mode === 'major' ? 'major' : 'minor';
        if (p.ring === tonicRing && p.index === index) score += 0.35 * w;
      });
      // Первый аккорд пьесы чаще всего тоника.
      const first = recent[recent.length - 1];
      if (first.index === index && first.ring === (mode === 'major' ? 'major' : 'minor')) score += 0.2;
      if (!best || score > best.score + 1e-9) best = { key, score };
    }
  }
  return best!.key;
}
