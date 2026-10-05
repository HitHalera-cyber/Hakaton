import { describe, expect, it } from 'vitest';
import { decodeWav, encodeWav } from '../src/core/export/wav';

describe('WAV для записи себя', () => {
  for (const bits of [16, 24] as const)
    it(`${bits} бит: туда и обратно без потерь (с точностью до шага)`, () => {
      const x = Float32Array.from({ length: 1000 }, (_, i) => 0.8 * Math.sin(i / 7) * (i % 3 ? 1 : -1));
      const buf = encodeWav(x, 48000, bits);
      expect(buf.byteLength).toBe(44 + 1000 * (bits / 8));
      const r = decodeWav(buf);
      expect(r.sampleRate).toBe(48000);
      expect(r.bits).toBe(bits);
      const step = 2 / 2 ** bits;
      for (let i = 0; i < x.length; i++) expect(Math.abs(r.samples[i] - x[i])).toBeLessThanOrEqual(step);
    });
  it('перегруз обрезается, а не переворачивается', () => {
    const r = decodeWav(encodeWav(Float32Array.from([1.5, -2]), 44100, 24));
    expect(r.samples[0]).toBeGreaterThan(0.99);
    expect(r.samples[1]).toBeLessThan(-0.99);
  });
});
