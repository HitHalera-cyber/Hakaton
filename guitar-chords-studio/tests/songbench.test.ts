// Замер точности разбора песни на «трудных» синтетических песнях.
// Метрика — доля времени, где аккорд назван верно по тонике и ладу (мажор/минор), как в MIREX majmin.
import { describe, expect, it } from 'vitest';
import { SONG_VOCAB } from '../src/core/analysis/chordRecognition';
import { decodeChords, extractFeatures, setKeyBonus, type SongFeatures } from '../src/core/analysis/songAnalysis';
import { parseChordSymbol } from '../src/core/music/chordParse';
import { GSR, makeSong, type SongSpec } from './helpers/songgen';

const majmin = (s: string) => {
  const p = parseChordSymbol(s);
  if (!p) return 'N';
  const minor = p.template.degrees.includes('b3') && !p.template.degrees.includes('3');
  return `${p.rootPc}${minor ? 'm' : ''}`;
};

const SPECS: (Omit<SongSpec, 'seed'> & { name: string })[] = [
  {
    name: 'поп, чисто',
    chords: ['Am', 'F', 'C', 'G', 'Am', 'F', 'C', 'G'],
    bpm: 110,
    beatsPerChord: 4,
    cents: 0,
    vocal: 0,
    drums: 0.5,
    noise: 0,
  },
  {
    name: 'с вокалом',
    chords: ['Em', 'C', 'G', 'D', 'Em', 'C', 'G', 'D'],
    bpm: 96,
    beatsPerChord: 4,
    cents: 0,
    vocal: 1.2,
    drums: 0.6,
    noise: 0.5,
  },
  {
    name: 'расстройка +40 ц',
    chords: ['Dm', 'G', 'C', 'Am', 'Dm', 'G', 'C', 'Am'],
    bpm: 124,
    beatsPerChord: 4,
    cents: 40,
    vocal: 0.8,
    drums: 0.6,
    noise: 0.5,
  },
  {
    name: 'расстройка −30 ц',
    chords: ['A', 'E', 'F#m', 'D', 'A', 'E', 'F#m', 'D'],
    bpm: 100,
    beatsPerChord: 4,
    cents: -30,
    vocal: 1,
    drums: 0.7,
    noise: 1,
  },
  {
    name: 'быстрые смены',
    chords: ['C', 'G', 'Am', 'F', 'C', 'G', 'F', 'C', 'Am', 'Em', 'F', 'G', 'C', 'G', 'Am', 'F'],
    bpm: 120,
    beatsPerChord: 2,
    cents: 15,
    vocal: 1,
    drums: 0.8,
    noise: 0.8,
  },
  {
    name: 'септаккорды',
    chords: ['Am7', 'D7', 'Gmaj7', 'Cmaj7', 'Am7', 'D7', 'Gmaj7', 'Cmaj7'],
    bpm: 90,
    beatsPerChord: 4,
    cents: -15,
    vocal: 0.8,
    drums: 0.5,
    noise: 0.5,
  },
  {
    name: 'громкий вокал',
    chords: ['C', 'Am', 'F', 'G', 'C', 'Am', 'F', 'G'],
    bpm: 104,
    beatsPerChord: 4,
    cents: 10,
    vocal: 3,
    drums: 0.8,
    noise: 1,
  },
  {
    name: 'четверть тона (+50 ц)',
    chords: ['E', 'B', 'C#m', 'A', 'E', 'B', 'C#m', 'A'],
    bpm: 116,
    beatsPerChord: 4,
    cents: 48,
    vocal: 1.2,
    drums: 0.7,
    noise: 1,
  },
  {
    name: 'баллада, минор',
    chords: ['Bm', 'G', 'D', 'A', 'Bm', 'G', 'Em', 'F#m'],
    bpm: 72,
    beatsPerChord: 4,
    cents: -20,
    vocal: 1.5,
    drums: 0.4,
    noise: 1,
  },
  {
    name: 'громкие ударные и шум',
    chords: ['G', 'D', 'Em', 'C', 'G', 'D', 'Em', 'C'],
    bpm: 140,
    beatsPerChord: 4,
    cents: 25,
    vocal: 1.4,
    drums: 1.6,
    noise: 2,
  },
];

/** «Как в жизни»: перегруз, ревербер, ходящий бас, клавишные. */
const HARD: (Omit<SongSpec, 'seed'> & { name: string })[] = [
  {
    name: 'рок: перегруз',
    chords: ['E', 'C', 'G', 'D', 'E', 'C', 'G', 'D'],
    bpm: 128,
    beatsPerChord: 4,
    cents: 0,
    vocal: 1.2,
    drums: 1.2,
    noise: 1,
    distortion: 4,
  },
  {
    name: 'зал: ревербер',
    chords: ['Am', 'F', 'C', 'G', 'Am', 'F', 'C', 'G'],
    bpm: 92,
    beatsPerChord: 4,
    cents: -10,
    vocal: 1.4,
    drums: 0.6,
    noise: 0.5,
    reverb: 0.8,
  },
  {
    name: 'ходящий бас',
    chords: ['C', 'Am', 'Dm', 'G', 'C', 'Am', 'Dm', 'G'],
    bpm: 112,
    beatsPerChord: 4,
    cents: 0,
    vocal: 1,
    drums: 0.8,
    noise: 0.5,
    walkingBass: true,
  },
  {
    name: 'клавишные + вокал',
    chords: ['D', 'Bm', 'G', 'A', 'D', 'Bm', 'G', 'A'],
    bpm: 84,
    beatsPerChord: 4,
    cents: 20,
    vocal: 2,
    drums: 0.5,
    noise: 0.8,
    pad: 1.5,
  },
  {
    name: 'всё сразу',
    chords: ['G', 'Em', 'C', 'D', 'G', 'Em', 'C', 'D'],
    bpm: 118,
    beatsPerChord: 4,
    cents: -25,
    vocal: 2,
    drums: 1.4,
    noise: 1.5,
    distortion: 3,
    reverb: 0.6,
    walkingBass: true,
    pad: 1,
  },
];

export function accuracy(spec: SongSpec, transform?: (f: SongFeatures, audio: Float32Array) => SongFeatures) {
  const song = makeSong(spec);
  let f = extractFeatures(song.audio, GSR);
  if (transform) f = transform(f, song.audio);
  const segs = decodeChords(f, SONG_VOCAB.simple, 2);
  let ok = 0;
  let n = 0;
  for (let t = 0.25; t < song.duration - 0.25; t += 0.05) {
    const seg = segs.find((s) => t >= s.start && t < s.end);
    const got = seg && seg.rootPc != null ? majmin(seg.symbol) : 'N';
    if (got === majmin(song.truthAt(t))) ok++;
    n++;
  }
  return { acc: ok / n, tuning: f.tuningCents };
}

describe('точность разбора песни (синтетика)', () => {
  if (process.env.KEY_BONUS) setKeyBonus(Number(process.env.KEY_BONUS));
  const results = [...SPECS, ...HARD].map((s, i) => ({ name: s.name, cents: s.cents, ...accuracy({ ...s, seed: 7 + i }) }));
  it('отчёт', () => {
    const mean = results.reduce((a, r) => a + r.acc, 0) / results.length;
    console.log(
      results.map((r) => `${r.name.padEnd(24)} ${(r.acc * 100).toFixed(1)}%  строй ${r.cents} → найден ${r.tuning}`).join('\n') +
        `\nсреднее ${(mean * 100).toFixed(1)}%`,
    );
    expect(mean).toBeGreaterThan(0);
  });
});

/**
 * Нейросеть в разборе песни (долго: ~1 мин на все песни) — только с NEURAL_BENCH=1:
 * формулы против формул + нейросети на тех же песнях.
 */
describe('разбор песни: формулы и нейросеть', () => {
  it.runIf(process.env.NEURAL_BENCH)(
    'сравнение',
    async () => {
      const { readFileSync } = await import('node:fs');
      const { loadBasicPitch } = await import('../src/core/analysis/neural/basicPitch');
      const { songActivations, beatFeaturesFromActivations, blendFeatures } = await import('../src/core/analysis/neural/songNeural');
      const dir = new URL('../public/models/basic-pitch/', import.meta.url);
      const net = await loadBasicPitch(
        {
          json: async () => JSON.parse(readFileSync(new URL('model.json', dir), 'utf8')),
          weights: async () => {
            const b = readFileSync(new URL('group1-shard1of1.bin', dir));
            return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
          },
        },
        (process.env.NEURAL_BACKEND as 'wasm' | 'cpu') ?? 'wasm',
        new URL('../node_modules/@tensorflow/tfjs-backend-wasm/dist/', import.meta.url).pathname,
      );
      const { tunedForModel } = await import('../src/core/analysis/neural/songNeural');
      const weights = (process.env.NEURAL_W ?? '0.3,0.45,0.6').split(',').map(Number);
      const rows: string[] = [];
      const sums = new Array(weights.length + 1).fill(0);
      const all = [...SPECS, ...HARD].filter((s) => !process.env.SONGS || process.env.SONGS.split(',').some((x) => s.name.includes(x)));
      for (const [i, s] of all.entries()) {
        const spec = { ...s, seed: 7 + [...SPECS, ...HARD].indexOf(s) };
        const song = makeSong(spec);
        const base = extractFeatures(song.audio, GSR);
        const tuned = tunedForModel(song.audio, GSR, base.tuningCents);
        const act = await songActivations(net, tuned.audio);
        const accs = [
          accuracy(spec).acc,
          ...weights.map(
            (w) => accuracy(spec, (f) => blendFeatures(f, beatFeaturesFromActivations(act, f.beats, f.duration, tuned.timeScale), w)).acc,
          ),
        ];
        accs.forEach((a, k) => (sums[k] += a));
        rows.push(
          `${s.name.padEnd(24)} ` + accs.map((a, k) => `${k ? 'w=' + weights[k - 1] : 'формулы'} ${(a * 100).toFixed(1)}%`).join('  '),
        );
        void i;
      }
      console.log(
        rows.join('\n') +
          '\nсреднее: ' +
          sums.map((x, k) => `${k ? 'w=' + weights[k - 1] : 'формулы'} ${((x / all.length) * 100).toFixed(1)}%`).join('  '),
      );
      const sn = sums[1];
      expect(sn).toBeGreaterThan(0);
    },
    1200000,
  );
});
