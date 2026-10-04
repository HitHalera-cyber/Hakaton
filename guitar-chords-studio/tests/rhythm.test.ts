import { describe, expect, it } from 'vitest';
import { attackIndex, beatError, lowShare, median } from '../src/core/practice/timing';
import { OnsetDetector, rmsOf } from '../src/services/mic';
import { SR, strum } from './helpers/strum';

/**
 * Модель «Ритма»: метроном щёлкает каждые 0,5 с, человек бьёт по струнам в долю, но звук приходит
 * с задержкой latency; программа читает микрофон кадрами по ~16 мс с дрожанием. Щелчки метронома
 * тоже попадают в микрофон (игра без наушников).
 */
function simulate(latency: number, clicks: boolean) {
  const beatDur = 0.5;
  const beats = Array.from({ length: 16 }, (_, i) => 1 + i * beatDur);
  const x = new Float32Array(Math.floor(10 * SR));
  const chord = strum('x32010', 1, 0.45);
  let seed = 5;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  beats.forEach((b, k) => {
    if (clicks) {
      const at = Math.floor((b + 0.02) * SR);
      for (let i = 0; i < 0.06 * SR; i++)
        x[at + i] += 0.25 * Math.sign(Math.sin((2 * Math.PI * 1175 * i) / SR)) * Math.exp(-i / (0.008 * SR));
    }
    if (k % 2 === 0) return; // человек играет каждую вторую долю — между ними только щелчки
    const at = Math.floor((b + latency + (rnd() - 0.5) * 0.01) * SR);
    for (let i = 0; i < chord.length && at + i < x.length; i++) x[at + i] += chord[i];
  });
  const onsets = new OnsetDetector(0.6, 0.1);
  const raw: number[] = [];
  let candidate: { t: number; peak: number; at: number } | null = null;
  let now = 0.3;
  while (now < 9.5) {
    now += 0.0167 + (rnd() - 0.5) * 0.008;
    const end = Math.floor(now * SR);
    const buf = x.subarray(end - 2048, end);
    const rms = rmsOf(buf, 512);
    if (candidate) {
      candidate.peak = Math.max(candidate.peak, rms);
      if (now - candidate.at >= 0.07) {
        if (rms >= candidate.peak * 0.35) raw.push(candidate.t);
        candidate = null;
      }
    }
    if (onsets.feed(rms, now) && !candidate) {
      const idx = attackIndex(buf);
      if (process.env.DBG) process.stderr.write(`onset ${now.toFixed(3)} low ${lowShare(buf, idx, SR).toFixed(2)}\n`);
      if (lowShare(buf, idx, SR) < 0.55) onsets.forget();
      else candidate = { t: now - (buf.length - idx) / SR, peak: rms, at: now };
    }
  }
  if (process.env.DBG) process.stderr.write(raw.map((t) => t.toFixed(3)).join(' ') + '\n');
  const errs = raw.map((t) => beatError(t, beats, beatDur, 1)).filter((e): e is number => e != null);
  return { count: raw.length, latency: median(errs), spread: Math.max(...errs.map((e) => Math.abs(e - median(errs)))) };
}

describe('ритм', () => {
  it('задержка измеряется точно, удары — без дрожания кадров', () => {
    const r = simulate(0.06, false);
    expect(r.count).toBe(8);
    // В синтезе удара первая звучащая струна (5-я) вступает через 15 мс.
    expect(Math.abs(r.latency - 0.075)).toBeLessThan(0.006);
    expect(r.spread).toBeLessThan(0.012);
  });
  it('щелчки метронома из колонок не считаются ударами', () => {
    const r = simulate(0.09, true);
    expect(r.count).toBe(8);
    expect(Math.abs(r.latency - 0.105)).toBeLessThan(0.008);
  });
});
