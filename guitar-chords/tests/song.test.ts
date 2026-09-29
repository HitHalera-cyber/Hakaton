import { describe, expect, it } from 'vitest';
import { SONG_VOCAB } from '../src/core/analysis/chordRecognition';
import {
  decodeChords,
  detectKey,
  extractFeatures,
  shapeName,
  smoothSegments,
  suggestCapo,
  type ChordSegment,
} from '../src/core/analysis/songAnalysis';
import { SR, strum } from './helpers/strum';

/** «Песня»: аккорды по 4 доли, бой на каждую долю, бочка и хай-хэт. */
function song(tabs: string[], bpm = 120, repeats = 2): Float32Array {
  const beat = 60 / bpm;
  const total = tabs.length * 4 * repeats;
  const out = new Float32Array(Math.ceil((total * beat + 1) * SR));
  let noise = 1;
  const rnd = () => ((noise = (noise * 16807) % 2147483647) / 2147483647) * 2 - 1;
  for (let b = 0; b < total; b++) {
    const t0 = Math.floor(b * beat * SR);
    const tab = tabs[Math.floor(b / 4) % tabs.length];
    const chord = strum(tab, 1, beat);
    for (let i = 0; i < chord.length && t0 + i < out.length; i++) out[t0 + i] += chord[i] * 0.7;
    // Бочка на каждую долю, хай-хэт — шум.
    for (let i = 0; i < SR * 0.08 && t0 + i < out.length; i++) {
      out[t0 + i] += 0.5 * Math.sin((2 * Math.PI * 55 * i) / SR) * Math.exp((-40 * i) / SR);
      out[t0 + i] += 0.08 * rnd() * Math.exp((-120 * i) / SR);
    }
  }
  return out;
}

const chordsOf = (segs: ChordSegment[]) => segs.filter((s) => s.rootPc != null && s.beats >= 2).map((s) => s.symbol);

describe('разбор песни', () => {
  const audio = song(['x32010', '320003', 'x02210', '133211']);
  const f = extractFeatures(audio, SR);

  it('находит темп', () => {
    expect(Math.abs(f.bpm - 120)).toBeLessThanOrEqual(6);
  });
  it('находит последовательность C – G – Am – F', () => {
    const seq = chordsOf(decodeChords(f, SONG_VOCAB.simple)).join(' ');
    expect(seq).toContain('C G Am F');
  });
  it('тональность — до мажор (или параллельный ля минор)', () => {
    const k = detectKey(f);
    expect([`0-major`, `9-minor`]).toContain(`${k.tonicPc}-${k.mode}`);
  });
  it('короткие «вспышки» аккордов поглощаются соседями', () => {
    const seg = (symbol: string, beats: number, start: number): ChordSegment => ({
      start,
      end: start + beats / 2,
      rootPc: 0,
      templateId: 'maj',
      symbol,
      nameRu: '',
      beats,
    });
    const out = smoothSegments([seg('C', 4, 0), seg('Em', 1, 2), seg('C', 3, 2.5), seg('G', 4, 4), seg('D', 1, 6), seg('Am', 4, 6.5)], 2);
    expect(out.map((s) => `${s.symbol}${s.beats}`).join(' ')).toBe('C8 G5 Am4');
  });
  it('каподастр: песню в ля мажоре удобнее играть с каподастром на 2 ладу', () => {
    const seg = (sym: string, rootPc: number, templateId: string): ChordSegment => ({
      start: 0,
      end: 4,
      rootPc,
      templateId,
      symbol: sym,
      nameRu: '',
      beats: 8,
    });
    const segs = [seg('A', 9, 'maj'), seg('E', 4, 'maj'), seg('F#m', 6, 'min'), seg('D', 2, 'maj')];
    const best = suggestCapo(segs)[0];
    expect(best.capo).toBe(2);
    expect(best.easyShare).toBe(1);
    expect(segs.map((s) => shapeName(s, 2)).join(' ')).toBe('G D Em C');
  });
});
