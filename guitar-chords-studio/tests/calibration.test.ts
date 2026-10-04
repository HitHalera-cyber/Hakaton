import { describe, expect, it } from 'vitest';
import { applyGains, buildCalibration, measureOpenString } from '../src/core/analysis/calibration';
import { SEMI_LO, SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { TUNINGS } from '../src/core/music/tunings';
import { SR } from './helpers/strum';

const STD = TUNINGS.standard.strings;
const N = 16384;
const analyzer = new SpectrumAnalyzer(N, SR);

/** Открытая струна: cents — расстройка, fund — громкость основного тона (микрофон «съедает» басы). */
function openString(midi: number, cents: number, fund: number): Float32Array {
  const f0 = 440 * Math.pow(2, (midi + cents / 100 - 69) / 12);
  const x = new Float32Array(N);
  for (let h = 1; h <= 8; h++) {
    const amp = (h === 1 ? fund : 1 / h) * 0.2;
    for (let i = 0; i < N; i++) x[i] += amp * Math.exp(-i / SR) * Math.sin((2 * Math.PI * f0 * h * i) / SR);
  }
  return x;
}

describe('калибровка', () => {
  // Микрофон теряет основной тон низких струн; 2-я струна (B) расстроена на −25 ц, вся гитара — на +10 ц.
  const fundOf = (m: number) => (m < 50 ? 0.12 : m < 57 ? 0.4 : 1);
  const centsOf = (s: number) => 10 + (s === 4 ? -35 : 0);
  const measured = STD.map((m, s) => {
    const x = openString(m, centsOf(s), fundOf(m));
    return measureOpenString(x.subarray(N - 8192), SR, analyzer.semitones(x, 0).semi, m);
  });
  const cal = buildCalibration(measured);

  it('строй каждой струны и общий сдвиг', () => {
    measured.forEach((m, s) => expect(Math.abs((m.cents ?? 999) - centsOf(s))).toBeLessThanOrEqual(4));
    expect(Math.abs(cal.tuningCents - 10)).toBeLessThanOrEqual(4);
  });

  it('басы поднимаются, верха не трогаются', () => {
    const gainAt = (m: number) => cal.gains[m - SEMI_LO];
    expect(gainAt(STD[0])).toBeGreaterThan(2);
    expect(gainAt(STD[1])).toBeGreaterThan(1.3);
    expect(gainAt(STD[3])).toBeCloseTo(1, 1);
    expect(gainAt(STD[5])).toBeCloseTo(1, 1);
    expect(gainAt(90)).toBe(1);
  });

  it('после калибровки основной тон низкой струны снова сильнее октавы', () => {
    const x = openString(STD[0], 10, fundOf(STD[0]));
    const semi = analyzer.semitones(x, 0).semi;
    const i = STD[0] - SEMI_LO;
    expect(semi[i]).toBeLessThan(semi[i + 12]);
    applyGains(semi, cal.gains);
    expect(semi[i]).toBeGreaterThan(semi[i + 12] * 0.7);
  });
});
