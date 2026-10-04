import { describe, expect, it } from 'vitest';
import { SpectrumAnalyzer } from '../src/core/analysis/dsp';
import { fretsToTab, pluckFromSpectra, solveFingering, type Pluck } from '../src/core/analysis/stringPick';
import { TUNINGS } from '../src/core/music/tunings';
import { SR, stringTone } from './helpers/strum';

const STD = TUNINGS.standard.strings;
const N = 16384;
const analyzer = new SpectrumAnalyzer(N, SR);
const LO = STD[0];
const HI = STD[5] + 15;

/**
 * Струны по одной: tab — аппликатура, '-' — струну не задели, 'm' — задели заглушённую (глухой стук).
 * Щипки через gap секунд. Возвращает щипки, как их услышит программа (спектр за 0,2 с после щипка
 * минус спектр до него).
 */
function pickStrings(tab: string, gap = 0.5, noise = 0): Pluck[] {
  const hits = [...tab].map((ch, s) => ({ ch, s })).filter((h) => h.ch !== '-' && h.ch !== 'x');
  const total = hits.length * gap + 1;
  const x = new Float32Array(Math.floor(total * SR) + N);
  let seed = 3;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 1073741824 - 1;
  hits.forEach((h, k) => {
    const at = Math.floor((0.4 + k * gap) * SR);
    if (h.ch === 'm') {
      for (let i = 0; i < 0.03 * SR; i++) x[at + i] += 0.25 * rnd() * Math.exp(-i / (0.006 * SR));
      return;
    }
    const tone = stringTone(STD[h.s] + parseInt(h.ch, 16), total);
    for (let i = 0; i < tone.length && at + i < x.length; i++) x[at + i] += tone[i];
  });
  for (let i = 0; i < x.length; i++) x[i] += noise * rnd();
  return hits.map((_, k) => {
    const at = (0.4 + k * gap) * SR;
    const pre = analyzer.semitones(x, Math.floor(at - N)).semi;
    const post = analyzer.semitones(x, Math.floor(at + 0.2 * SR - N)).semi;
    return pluckFromSpectra(pre, post, LO, HI);
  });
}

const solve = (tab: string, gap?: number, noise?: number) => {
  const r = solveFingering(pickStrings(tab, gap, noise), STD);
  return r ? fretsToTab(r.frets) : null;
};

describe('режим «по струнам»', () => {
  it('все шесть струн — точная аппликатура', () => {
    expect(solve('320003')).toBe('320003');
    expect(solve('022100')).toBe('022100');
    expect(solve('133211')).toBe('133211');
  });
  it('баррэ выше по грифу отличается от открытой формы', () => {
    expect(solve('8(10)(10)988'.replace(/\((\d+)\)/g, (_, n) => (+n).toString(16)))).toBe('8(10)(10)988');
    expect(solve('x35553')).toBe('x35553');
  });
  it('басовую струну не задели — раскладка всё равно верная', () => {
    expect(solve('-32010')).toBe('x32010');
    expect(solve('--0232')).toBe('xx0232');
  });
  it('глухой щипок по заглушённой струне — X', () => {
    expect(solve('m32010')).toBe('x32010');
    expect(solve('mm0232')).toBe('xx0232');
  });
  it('быстро и с шумом', () => {
    expect(solve('x02210'.replace('x', '-'), 0.3, 0.004)).toBe('x02210');
  });
});

describe('«по струнам»: весь путь от звука до аппликатуры', () => {
  it('щипки поверх звенящих струн ловятся и раскладываются', async () => {
    const { PluckTracker } = await import('../src/core/analysis/stringPick');
    const { OnsetDetector, attackOf, rmsOf } = await import('../src/services/mic');
    const tabs = ['x32010', 'x35553', '320003'];
    // Звук: аккорды по струнам (щипок раз в 0,5 с), между аккордами 2,5 с.
    const x = new Float32Array(16 * SR);
    let t = 2.5;
    for (const tab of tabs) {
      for (let s = 0; s < 6; s++) {
        if (tab[s] === 'x') continue;
        const tone = stringTone(STD[s] + parseInt(tab[s], 16), 3.5);
        const at = Math.floor(t * SR);
        for (let i = 0; i < tone.length && at + i < x.length; i++) x[at + i] += tone[i] * 1.5;
        t += 0.5;
      }
      t += 2.5;
    }
    const loud = new OnsetDetector(0.5);
    const hf = new OnsetDetector(0.6, 0.16);
    const tracker = new PluckTracker();
    let pending: { at: number; pre: Float32Array } | null = null;
    let plucks: Pluck[] = [];
    let last = -10;
    const found: string[] = [];
    for (let end = N; end < x.length; end += 800) {
      const buf = x.subarray(end - N, end);
      const now = end / SR;
      const semi = analyzer.semitones(buf, 0).semi;
      const quick = loud.feed(rmsOf(buf), now) || hf.feed(attackOf(buf), now);
      if (pending && now - pending.at >= 0.2) {
        plucks.push(pluckFromSpectra(pending.pre, semi, LO, HI));
        pending = null;
        last = now;
      }
      const hit = tracker.feed(now, semi, quick);
      if (hit) pending = hit;
      if (!pending && plucks.length && (now - last > 1.5 || plucks.length === 6)) {
        const f = solveFingering(plucks, STD);
        found.push(f ? fretsToTab(f.frets) : '?');
        plucks = [];
      }
    }
    expect(found).toEqual(tabs);
  });
});

describe('проверка аппликатуры по струнам', () => {
  it('ошибки постановки находятся по каждой струне', async () => {
    const { alignPluck, judgeString } = await import('../src/core/analysis/fingerCheck');
    // Нужен C (x32010). Сыграно: 6-я не заглушена и звенит (E2), 2-я не прижата (B3 вместо C4),
    // 3-я заглушена пальцем (глухой стук), остальные верно.
    const played = pickStrings('032m00'.replace('m', 'm'));
    // pickStrings понимает 'm' как глухой щипок; струны: 6:E2 5:C3 4:E3 3:глухо 2:B3(открытая) 1:E4
    const expected = [null, 48, 52, 55, 60, 64].map((midi, s) => ({ string: s, midi, openMidi: STD[s] }));
    if (process.env.DBG) process.stderr.write(JSON.stringify(played) + '\n');
    const verdicts: Record<number, string> = {};
    let cursor = 0;
    for (const p of played) {
      const s = alignPluck(expected, cursor, p);
      verdicts[s] = judgeString(expected[s], p).status;
      cursor = s + 1;
    }
    expect(verdicts).toEqual({ 0: 'ringing', 1: 'ok', 2: 'ok', 3: 'missing', 4: 'open', 5: 'ok' });
  });

  it('пропущенный щипок не сдвигает остальные струны', async () => {
    const { alignPluck } = await import('../src/core/analysis/fingerCheck');
    const expected = [null, 48, 52, 55, 60, 64].map((midi, s) => ({ string: s, midi, openMidi: STD[s] }));
    // Программа не услышала щипок 5-й струны: первым пришёл E3 (4-я).
    expect(alignPluck(expected, 1, { midi: 52, clarity: 0.8 })).toBe(2);
    expect(alignPluck(expected, 1, { midi: 48, clarity: 0.8 })).toBe(1);
  });
});

describe('«по струнам»: 1-я струна поверх звенящих', () => {
  it('ми 1-й струны не превращается в ля из-за слабого прироста на 5-й', () => {
    const n = 84;
    const pre = new Float32Array(n);
    const post = new Float32Array(n);
    const add = (arr: Float32Array, midi: number, amp: number) => {
      for (const [off, w] of [
        [0, 1],
        [12, 0.5],
        [19, 0.35],
        [24, 0.25],
        [28, 0.2],
      ])
        if (midi + off - 24 < n) arr[midi + off - 24] += amp * w;
    };
    // Звенят струны аккорда (ля 5-й открытой — громко), щипок 1-й струны (ми) — тихий.
    for (const m of [45, 52, 57, 60]) {
      add(pre, m, 1);
      add(post, m, 0.95);
    }
    post[45 - 24] = pre[45 - 24] * 1.15; // биения: ля на мгновение громче
    add(post, 64, 0.35);
    const p = pluckFromSpectra(pre, post, 40, 79);
    expect(p.midi).toBe(64);
  });
});
