import { describe, expect, it } from 'vitest';
import { LIVE_VOCAB, buildModels } from '../src/core/analysis/chordRecognition';
import { SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { recognizeSound } from '../src/core/analysis/liveSound';
import { SR, strum } from './helpers/strum';

const analyzer = new SpectrumAnalyzer(16384, SR);
const models = buildModels(LIVE_VOCAB);

/** Накопленный спектр трёх окон после удара — как в живом режиме. */
function hear(tab: string, noise = 0, a = analyzer) {
  const x = strum(tab);
  let seed = 7;
  for (let i = 0; i < x.length; i++) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    x[i] += noise * (seed / 1073741824 - 1);
  }
  const acc = new Float32Array(analyzer.semitones(x, 0).semi.length);
  for (const start of [0.12, 0.2, 0.28]) {
    const { semi } = a.semitones(x, Math.floor(start * SR));
    for (let i = 0; i < acc.length; i++) acc[i] += semi[i];
  }
  return recognizeSound(acc, models);
}

describe('что звучит: нота, интервал или аккорд', () => {
  it('одна струна — нота', () => {
    expect(hear('xxxxx0').notes).toMatchObject({ kind: 'note', label: 'E4' });
    expect(hear('xx2xxx').notes).toMatchObject({ kind: 'note', label: 'E3' });
    expect(hear('x3xxxx').notes).toMatchObject({ kind: 'note', label: 'C3' });
  });
  it('две ноты — интервал', () => {
    const r = hear('x02xxx'); // A2 + E3 — квинта
    expect(r.notes?.kind).toBe('interval');
    expect(r.notes?.label).toBe('A + E');
    expect(r.notes?.nameRu).toContain('пауэр-аккорд A5');
    expect(hear('xxx0x0').notes?.label).toBe('G + E'); // G3 + E4 — секста
  });
  it('аккорды остаются аккордами', () => {
    for (const [tab, sym] of [
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
    ]) {
      const r = hear(tab);
      expect(r.notes, tab).toBeNull();
      expect(r.best?.symbol, tab).toBe(sym);
    }
  });
  it('шумный микрофон: нота и аккорд различаются', () => {
    expect(hear('xxxxx0', 0.06).notes).toMatchObject({ kind: 'note', label: 'E4' });
    expect(hear('x02xxx', 0.06).notes?.kind).toBe('interval');
    expect(hear('x02210', 0.06).best?.symbol).toBe('Am');
  });
});
