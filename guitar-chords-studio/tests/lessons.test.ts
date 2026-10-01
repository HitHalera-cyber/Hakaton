import { describe, expect, it } from 'vitest';
import { TUNINGS } from '../src/core/music/tunings';
import { voicingOptions } from '../src/core/songbook/voicingPlan';
import { LESSONS, LEVELS } from '../src/modules/lessons/lessons';
import { PATTERNS } from '../src/core/audio/patterns';

const STD = TUNINGS.standard.strings;

describe('уроки', () => {
  it('у каждого аккорда есть аппликатура, у боя — схема', () => {
    const bad: string[] = [];
    for (const l of LESSONS)
      for (const s of l.steps) {
        const chords = s.kind === 'change' ? s.pair : s.kind === 'info' ? (s.chord ? [s.chord] : []) : [s.chord];
        for (const c of chords) if (!voicingOptions(c, STD, 0, 1).length) bad.push(`${l.id}: ${c}`);
        if (s.kind === 'strum' && !PATTERNS.some((p) => p.id === s.patternId)) bad.push(`${l.id}: бой ${s.patternId}`);
      }
    expect(bad).toEqual([]);
  });
  it('уникальные id и известные уровни', () => {
    expect(new Set(LESSONS.map((l) => l.id)).size).toBe(LESSONS.length);
    for (const l of LESSONS) expect(LEVELS.some((v) => v.id === l.level)).toBe(true);
    expect(LESSONS.length).toBeGreaterThanOrEqual(18);
  });
});
