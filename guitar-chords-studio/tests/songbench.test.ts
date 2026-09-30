// Замер точности разбора песни на «трудных» синтетических песнях.
// Метрика — доля времени, где аккорд назван верно по тонике и ладу (мажор/минор), как в MIREX majmin.
import { describe, expect, it } from 'vitest';
import { SONG_VOCAB } from '../src/core/analysis/chordRecognition';
import { decodeChords, extractFeatures, setKeyBonus } from '../src/core/analysis/songAnalysis';
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

export function accuracy(spec: SongSpec) {
  const song = makeSong(spec);
  const f = extractFeatures(song.audio, GSR);
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
  const results = SPECS.map((s, i) => ({ name: s.name, cents: s.cents, ...accuracy({ ...s, seed: 7 + i }) }));
  it('отчёт', () => {
    const mean = results.reduce((a, r) => a + r.acc, 0) / results.length;
    console.log(
      results.map((r) => `${r.name.padEnd(24)} ${(r.acc * 100).toFixed(1)}%  строй ${r.cents} → найден ${r.tuning}`).join('\n') +
        `\nсреднее ${(mean * 100).toFixed(1)}%`,
    );
    expect(mean).toBeGreaterThan(0);
  });
});
