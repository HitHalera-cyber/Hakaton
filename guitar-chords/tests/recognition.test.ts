import { describe, expect, it } from 'vitest';
import { LIVE_VOCAB, buildModels, recognizeChord } from '../src/core/analysis/chordRecognition';
import { SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { SR, strum } from './helpers/strum';

const analyzer = new SpectrumAnalyzer(16384, SR);
const models = buildModels(LIVE_VOCAB);

function recognize(tab: string, bright = 1) {
  const x = strum(tab, bright);
  // Среднее по нескольким окнам после удара — как в живом режиме.
  const chroma = new Float32Array(12);
  const bass = new Float32Array(12);
  for (const start of [0.12, 0.2, 0.28]) {
    const f = analyzer.frame(x, Math.floor(start * SR));
    for (let i = 0; i < 12; i++) {
      chroma[i] += f.chroma[i];
      bass[i] += f.bass[i];
    }
  }
  return recognizeChord(chroma, bass, models);
}

const cases: [string, string][] = [
  ['x32010', 'C'],
  ['x02210', 'Am'],
  ['320003', 'G'],
  ['022100', 'E'],
  ['xx0232', 'D'],
  ['133211', 'F'],
  ['022030', 'Em7'],
  ['320001', 'G7'],
  ['xx0233', 'Dsus4'],
  ['x32000', 'Cmaj7'],
  ['xx0231', 'Dm'],
  ['022000', 'Em'],
  ['x02020', 'A7'],
  ['x24432', 'Bm'],
  ['244222', 'F#m'],
  ['x35553', 'C'],
];

describe('распознавание живого аккорда (синтез струны)', () => {
  it('большинство типичных аккордов распознаются', () => {
    const wrong = cases.filter(([tab, symbol]) => recognize(tab).best?.symbol !== symbol);
    expect(wrong.length, 'ошибки: ' + wrong.map((w) => w.join('→')).join(', ')).toBeLessThanOrEqual(2);
  });
  it('мажор и минор различаются', () => {
    expect(recognize('x02210').best?.symbol).toBe('Am');
    expect(recognize('x32010').best?.symbol).toBe('C');
    expect(recognize('022000').best?.symbol).toBe('Em');
    expect(recognize('022100').best?.symbol).toBe('E');
  });
  it('мягкий и яркий тембр тоже', () => {
    expect(recognize('x02210', 0.7).best?.symbol).toBe('Am');
    expect(recognize('320003', 1.5).best?.symbol).toBe('G');
  });
  it('уверенность — число 0..1', () => {
    const r = recognize('x32010');
    expect(r.best!.confidence).toBeGreaterThan(0.3);
    expect(r.best!.confidence).toBeLessThanOrEqual(1);
  });
  it('тишина — нет аккорда', () => {
    const f = analyzer.frame(new Float32Array(20000), 0);
    expect(recognizeChord(f.chroma, f.bass, models).best).toBeNull();
  });
});
