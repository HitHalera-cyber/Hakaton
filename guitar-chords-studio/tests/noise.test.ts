// Шумодав: посторонние звуки не должны превращаться в аккорды, а аккорды — отсеиваться.
import { describe, expect, it } from 'vitest';
import { SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { looksLikeGuitar, soundQuality } from '../src/core/analysis/liveSound';
import { SR, strum } from './helpers/strum';

const N = 16384;
const an = new SpectrumAnalyzer(N, SR);
let seed = 11;
const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 1073741824 - 1;

/** Кадры спектра так же, как в «По удару»: с 0,36 с после звука, раз в 0,09 с, до 1,2 с. */
function frames(x: Float32Array): Float32Array[] {
  const out: Float32Array[] = [];
  for (let t = 0.36; t < 1.2; t += 0.09) {
    const end = Math.floor(t * SR);
    if (end > x.length) break;
    out.push(an.semitones(x, Math.max(0, end - N)).semi);
  }
  return out;
}

/** «Речь»: гласные с плавающей высотой (100–220 Гц), слоги по 0,15–0,25 с, с формантами. */
function speech(): Float32Array {
  const x = new Float32Array(Math.floor(1.3 * SR));
  let phase = 0;
  for (let i = 0; i < x.length; i++) {
    const t = i / SR;
    const syl = Math.floor(t / 0.2);
    const f0 = 120 + 60 * Math.sin(syl * 1.7) + 25 * Math.sin(2 * Math.PI * 3 * t);
    phase += (2 * Math.PI * f0) / SR;
    const env = Math.max(0, Math.sin(Math.PI * ((t % 0.2) / 0.2)));
    let v = 0;
    for (let h = 1; h <= 20; h++) {
      const f = f0 * h;
      const formant = Math.exp(-(((f - 700 - 200 * Math.sin(syl)) / 250) ** 2)) + 0.6 * Math.exp(-(((f - 1800) / 400) ** 2)) + 0.15;
      v += (formant / h) * Math.sin(phase * h);
    }
    x[i] = 0.15 * env * v + 0.01 * rnd();
  }
  return x;
}
/** Хлопок / стук: короткий шумовой всплеск и эхо комнаты. */
function clap(): Float32Array {
  const x = new Float32Array(Math.floor(1.3 * SR));
  for (let i = 0; i < x.length; i++) x[i] = 0.5 * rnd() * Math.exp(-i / (0.25 * SR));
  return x;
}
/** Свист: чистый тон, высота скользит. */
function whistle(): Float32Array {
  const x = new Float32Array(Math.floor(1.3 * SR));
  let ph = 0;
  for (let i = 0; i < x.length; i++) {
    ph += (2 * Math.PI * (900 + 300 * Math.sin((2 * Math.PI * 1.2 * i) / SR))) / SR;
    x[i] = 0.2 * Math.sin(ph);
  }
  return x;
}
/** Шум улицы / вентилятор: розоватый шум. */
function hiss(): Float32Array {
  const x = new Float32Array(Math.floor(1.3 * SR));
  let y = 0;
  for (let i = 0; i < x.length; i++) x[i] = y = 0.97 * y + 0.05 * rnd();
  return x;
}

describe('шумодав', () => {
  it('аккорды проходят', () => {
    for (const tab of ['x32010', 'x02210', '320003', 'xx0232', '133211', '022000']) {
      const q = soundQuality(frames(strum(tab, 1, 1.3)));
      if (process.env.DBG) process.stderr.write(`${tab} ${JSON.stringify(q)}\n`);
      expect(looksLikeGuitar(q), `${tab}: ${JSON.stringify(q)}`).toBe(true);
    }
  });
  it('аккорды на шумном микрофоне тоже проходят', () => {
    for (const tab of ['x32010', 'x02210', '320003', 'xx0232', '133211', '022000']) {
      const x = strum(tab, 0.8, 1.3);
      for (let i = 0; i < x.length; i++) x[i] += 0.03 * rnd() + 0.02 * Math.sin((2 * Math.PI * 50 * i) / SR);
      const q = soundQuality(frames(x));
      if (process.env.DBG) process.stderr.write(`шумно ${tab} ${JSON.stringify(q)}\n`);
      expect(looksLikeGuitar(q), `${tab}: ${JSON.stringify(q)}`).toBe(true);
    }
  });
  it('одна струна тоже проходит', () => {
    expect(looksLikeGuitar(soundQuality(frames(strum('xxxxx0', 1, 1.3))))).toBe(true);
  });
  it('речь, хлопок, свист и шум — нет', () => {
    for (const [name, x] of [
      ['речь', speech()],
      ['хлопок', clap()],
      ['свист', whistle()],
      ['шум', hiss()],
    ] as const) {
      const q = soundQuality(frames(x));
      if (process.env.DBG) process.stderr.write(`${name} ${JSON.stringify(q)}\n`);
      expect(looksLikeGuitar(q), `${name}: ${JSON.stringify(q)}`).toBe(false);
    }
  });
});
