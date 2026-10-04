// Нейросеть Basic Pitch на синтезированных аккордах. Расчёт на процессоре без видеокарты — небыстрый,
// поэтому полный прогон только с NEURAL_BENCH=1; без него — одна быстрая проверка.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { LIVE_VOCAB, buildModels } from '../src/core/analysis/chordRecognition';
import { SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { recognizeNotes, recognizeSound } from '../src/core/analysis/liveSound';
import { BP_RATE, loadBasicPitch, notesFromActivations, resample } from '../src/core/analysis/neural/basicPitch';
import { SR, strum } from './helpers/strum';

const dir = new URL('../public/models/basic-pitch/', import.meta.url);
const files = {
  json: async () => JSON.parse(readFileSync(new URL('model.json', dir), 'utf8')),
  weights: async () => {
    const b = readFileSync(new URL('group1-shard1of1.bin', dir));
    return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
  },
};
const models = buildModels(LIVE_VOCAB);
const analyzer = new SpectrumAnalyzer(16384, SR);

const CASES: [string, string][] = [
  ['x32010', 'C'],
  ['x02210', 'Am'],
  ['320003', 'G'],
  ['022100', 'E'],
  ['xx0232', 'D'],
  ['133211', 'F'],
  ['xx0231', 'Dm'],
  ['022000', 'Em'],
  ['320001', 'G7'],
  ['x24432', 'Bm'],
  ['x02020', 'A7'],
  ['x35553', 'C'],
];

describe('нейросеть Basic Pitch', () => {
  it('загружается и слышит одну ноту', async () => {
    const net = await loadBasicPitch(files, 'cpu');
    const act = await net.run(resample(strum('xxxxx0', 1, 1), SR, BP_RATE));
    const notes = notesFromActivations(act, 0.1, 0.9);
    expect(notes[0]?.midi).toBe(64);
  }, 60000);

  it.runIf(process.env.NEURAL_BENCH)(
    'сравнение с формулами на аккордах',
    async () => {
      const backend = (process.env.NEURAL_BACKEND as 'wasm' | 'cpu') ?? 'cpu';
      const net = await loadBasicPitch(
        files,
        backend,
        new URL('../node_modules/@tensorflow/tfjs-backend-wasm/dist/', import.meta.url).pathname,
      );
      const t0 = performance.now();
      const rows: string[] = [];
      let nOk = 0;
      let dOk = 0;
      const noise = Number(process.env.NEURAL_NOISE ?? 0);
      const bright = Number(process.env.NEURAL_BRIGHT ?? 1);
      for (const [tab, sym] of CASES) {
        // Перед ударом 0,6 с тишины (в ней тот же шум) — как в жизни: шум звучит постоянно.
        const PRE = 0.6;
        const chord = strum(tab, bright, 1.2);
        const x = new Float32Array(Math.floor(PRE * SR) + chord.length);
        x.set(chord, Math.floor(PRE * SR));
        // До удара звенит прошлый аккорд (как в живой игре): у него общие ноты с новым.
        if (process.env.NEURAL_PREV) {
          const prev = strum(tab === 'x32010' ? 'x02210' : 'x32010', bright, 1.2);
          for (let i = 0; i < x.length; i++) x[i] += (prev[i + Math.floor(0.6 * SR)] ?? 0) * (i < PRE * SR ? 1 : 0.5);
        }
        let seed = 9;
        for (let i = 0; i < x.length; i++) {
          seed = (seed * 1103515245 + 12345) % 2147483648;
          x[i] += noise * (seed / 1073741824 - 1) + noise * 0.8 * Math.sin((2 * Math.PI * 50 * i) / SR);
        }
        const act = await net.run(resample(x, SR, BP_RATE));
        const notes = notesFromActivations(act, PRE + 0.1, PRE + 1.1, 0.3, PRE).filter((q) => q.midi >= 40);
        const n = recognizeNotes(notes, models).best?.symbol ?? '—';
        const acc = new Float32Array(analyzer.semitones(x, 0).semi.length);
        for (const st of [PRE + 0.12, PRE + 0.2, PRE + 0.28])
          analyzer.semitones(x, Math.floor(st * SR)).semi.forEach((v, i) => (acc[i] += v));
        const d = recognizeSound(acc, models).best?.symbol ?? '—';
        nOk += +(n === sym);
        dOk += +(d === sym);
        rows.push(`${tab} ${sym}: нейросеть ${n} [${notes.map((q) => q.midi).join(' ')}], формулы ${d}`);
      }
      process.stderr.write(
        rows.join('\n') +
          `\nнейросеть ${nOk}/${CASES.length}, формулы ${dOk}/${CASES.length}; ${net.backend}: ${Math.round((performance.now() - t0) / CASES.length)} мс на аккорд\n`,
      );
      expect(nOk).toBeGreaterThan(0);
    },
    600000,
  );
});
