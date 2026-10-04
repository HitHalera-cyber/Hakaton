import { describe, expect, it } from 'vitest';
import { beatError, median } from '../src/core/practice/timing';
import { StrumHitDetector } from '../src/services/hitDetector';
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
  const hits = new StrumHitDetector(true);
  const raw: number[] = [];
  let now = 0.3;
  while (now < 9.5) {
    now += 0.0167 + (rnd() - 0.5) * 0.008;
    const end = Math.floor(now * SR);
    const t = hits.feed(x.subarray(end - 2048, end), now, SR);
    if (t != null) raw.push(t);
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

/** Бой без пауз: струны звенят, следующий удар — поверх; микрофон ноутбука (басов почти нет). */
function continuous(filter: boolean, laptop: boolean, beatDur = 0.5) {
  const beats = Array.from({ length: 16 }, (_, i) => 1 + i * beatDur);
  const x = new Float32Array(Math.floor(10 * SR));
  let seed = 9;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const notes = [48, 52, 55, 60, 64]; // до мажор
  beats.forEach((b, k) => {
    const at = Math.floor((b + 0.05) * SR);
    const vol = 0.6 + rnd() * 0.5;
    notes.forEach((m, s) => {
      const f0 = 440 * 2 ** ((m - 69) / 12);
      const off = Math.floor((k % 2 ? 4 - s : s) * 0.012 * SR); // вниз / вверх
      for (let h = 1; h <= 8; h++) {
        const amp = (0.12 * vol) / h;
        const dec = 0.6 + h * 0.5;
        for (let i = 0; i < 3 * SR && at + off + i < x.length; i++)
          x[at + off + i] += amp * Math.exp((-dec * i) / SR) * Math.sin((2 * Math.PI * f0 * h * i) / SR + h + s);
      }
    });
  });
  if (laptop) {
    // Микрофон ноутбука: срез ниже ~300 Гц.
    const a = Math.exp((-2 * Math.PI * 300) / SR);
    let y = 0;
    let prev = 0;
    for (let i = 0; i < x.length; i++) {
      y = a * (y + x[i] - prev);
      prev = x[i];
      x[i] = y;
    }
  }
  for (let i = 0; i < x.length; i++) x[i] += (rnd() - 0.5) * 0.002;
  const hits = new StrumHitDetector(filter);
  const raw: number[] = [];
  let now = 0.3;
  while (now < 9.5) {
    now += 0.0167 + (rnd() - 0.5) * 0.008;
    const end = Math.floor(now * SR);
    const t = hits.feed(x.subarray(end - 2048, end), now, SR);
    if (t != null) raw.push(t);
  }
  const errs = raw.map((t) => beatError(t, beats, beatDur, 1)).filter((e): e is number => e != null);
  if (process.env.DBG) process.stderr.write(raw.map((t) => t.toFixed(3)).join(' ') + '\n');
  return { count: raw.length, good: errs.filter((e) => Math.abs(e - 0.05) < 0.03).length };
}

describe('ритм: бой без пауз', () => {
  for (const laptop of [false, true])
    for (const filter of [false, true])
      it(`${laptop ? 'микрофон ноутбука' : 'полный звук'}, шумодав ${filter ? 'вкл' : 'выкл'}`, { timeout: 30000 }, () => {
        const r = continuous(filter, laptop);
        if (process.env.DBG) process.stderr.write(`${laptop} ${filter} ${JSON.stringify(r)}\n`);
        // Удары с 1,05 по 8,55 с — после первых 0,6 с замера фона ловятся все 16 (кроме первого-второго).
        expect(r.good).toBeGreaterThanOrEqual(14);
        expect(r.count - r.good).toBeLessThanOrEqual(1);
      });
});
