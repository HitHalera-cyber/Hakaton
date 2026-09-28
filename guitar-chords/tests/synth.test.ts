import { describe, expect, it } from 'vitest';
import { TIMBRES, renderPluck } from '../src/audio/guitarSynth';
import { midiToFreq } from '../src/music/notes';

/** Оценка частоты основного тона по автокорреляции с параболической интерполяцией. */
function estimatePitch(x: Float32Array, sr: number, expected: number): number {
  const seg = x.subarray(Math.floor(sr * 0.1), Math.floor(sr * 0.1) + 8192);
  const lo = Math.floor(sr / (expected * 1.3));
  const hi = Math.ceil(sr / (expected / 1.3));
  const ac = (lag: number) => {
    let s = 0;
    for (let i = 0; i + lag < seg.length; i++) s += seg[i] * seg[i + lag];
    return s;
  };
  let best = lo;
  let bestV = -Infinity;
  for (let lag = lo; lag <= hi; lag++) {
    const v = ac(lag);
    if (v > bestV) {
      bestV = v;
      best = lag;
    }
  }
  const a = ac(best - 1), b = ac(best), c = ac(best + 1);
  const shift = (0.5 * (a - c)) / (a - 2 * b + c);
  return sr / (best + shift);
}

describe('синтез струны', () => {
  for (const midi of [38, 40, 52, 64, 76, 79]) {
    it(`MIDI ${midi} строит точнее 5 центов`, () => {
      const sr = 48000;
      const f = midiToFreq(midi);
      const x = renderPluck(sr, midi, TIMBRES.acoustic);
      const est = estimatePitch(x, sr, f);
      const cents = 1200 * Math.log2(est / f);
      expect(Math.abs(cents)).toBeLessThan(5);
      expect(x.every((v) => Number.isFinite(v) && Math.abs(v) <= 1)).toBe(true);
    });
  }
});
