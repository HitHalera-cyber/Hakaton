import { describe, expect, it } from 'vitest';
import { SEMI_COUNT, SEMI_LO } from '../src/core/analysis/dsp';
import { checkFingering } from '../src/core/analysis/fingerCheck';
import { MelodyTracker, melodyTab, placeOnFretboard } from '../src/core/analysis/melody';
import { TUNINGS } from '../src/core/music/tunings';
import { matchesChord } from '../src/core/practice/chordMatch';
import { lastDays, streak, totalMinutes } from '../src/core/practice/stats';
import { beatError, timingSummary } from '../src/core/practice/timing';
import {
  chordsToBars,
  importChordsOverText,
  parseChordPro,
  songChords,
  transposeBody,
  transposeSymbol,
} from '../src/core/songbook/chordpro';
import { handPosition, planVoicings, transitionCost, voicingOptions } from '../src/core/songbook/voicingPlan';

const STD = TUNINGS.standard.strings; // E2 A2 D3 G3 B3 E4

describe('песенник: ChordPro', () => {
  it('разбирает аккорды над слогами и разделы', () => {
    const lines = parseChordPro('{Припев}\n[Am]Вот новый [F]поворот\n\nбез аккордов');
    expect(lines[0]).toEqual({ kind: 'section', title: 'Припев' });
    expect(lines[1]).toEqual({
      kind: 'lyrics',
      parts: [
        { chord: 'Am', text: 'Вот новый ' },
        { chord: 'F', text: 'поворот' },
      ],
    });
    expect(lines[2]).toEqual({ kind: 'empty' });
    expect(lines[3]).toEqual({ kind: 'lyrics', parts: [{ chord: undefined, text: 'без аккордов' }] });
  });

  it('собирает аккорды песни по порядку появления', () => {
    expect(songChords('[Am]раз [F]два [Am]три [G7]четыре [xyz]')).toEqual(['Am', 'F', 'G7']);
  });

  it('транспонирует аккорды с басом и оставляет непонятные', () => {
    expect(transposeSymbol('Am', 2)).toBe('Bm');
    expect(transposeSymbol('C/E', 2)).toBe('D/F#');
    expect(transposeSymbol('G7', -2)).toBe('F7');
    expect(transposeBody('[Am]раз [N.C.]два', 3)).toBe('[Cm]раз [N.C.]два');
  });

  it('импортирует строку аккордов над строкой текста', () => {
    const src = 'Am        F\nВот новый поворот\nC  G\n\nПросто текст';
    expect(importChordsOverText(src)).toBe('[Am]Вот новый [F]поворот\n[C] [G]\n\nПросто текст');
  });

  it('раскладывает аккорды разбора по тактам', () => {
    const bars = chordsToBars([
      { symbol: 'Am', beats: 4 },
      { symbol: 'F', beats: 2 },
      { symbol: 'G', beats: 2 },
      { symbol: 'C', beats: 8 },
    ]);
    expect(bars).toBe('| [Am] | [F] [G] | [C] | % |');
  });
});

describe('аппликатуры по умолчанию', () => {
  it('для открытых аккордов первой идёт привычная открытая форма', () => {
    const first = (c: string) =>
      voicingOptions(c, STD, 0, 1)[0]
        .frets.map((f) => (f == null ? 'x' : f))
        .join('');
    expect(first('Am')).toBe('x02210');
    expect(first('C')).toBe('x32010');
    expect(first('E')).toBe('022100');
    expect(first('Em')).toBe('022000');
    expect(first('D')).toBe('xx0232');
    expect(first('Dm')).toBe('xx0231');
  });
});

describe('песенник: удобные переходы', () => {
  it('позиция руки и стоимость перехода', () => {
    expect(handPosition([null, 3, 2, 0, 1, 0])).toBe(2);
    expect(transitionCost([null, 0, 2, 2, 1, 0], [null, 0, 2, 2, 1, 0])).toBe(0);
    expect(transitionCost([null, 0, 2, 2, 1, 0], [8, 10, 10, 9, 8, 8])).toBeGreaterThan(10);
  });

  it('для открытых аккордов выбирает открытые формы в первой позиции', () => {
    const plan = planVoicings(['Am', 'F', 'C', 'G', 'Am', 'F', 'C', 'G'], STD, 0);
    expect(Object.keys(plan).sort()).toEqual(['Am', 'C', 'F', 'G']);
    for (const frets of Object.values(plan)) expect(handPosition(frets)).toBeLessThanOrEqual(3);
  });
});

/** Спектр «аккорда»: ноты с обертонами. */
function spectrum(notes: { midi: number; amp?: number }[]) {
  const semi = new Float32Array(SEMI_COUNT);
  for (const { midi, amp = 1 } of notes)
    for (const [off, w] of [
      [0, 1],
      [12, 0.6],
      [19, 0.4],
      [24, 0.3],
    ])
      if (midi + off - SEMI_LO < SEMI_COUNT) semi[midi + off - SEMI_LO] += amp * w;
  return semi;
}

describe('проверка аппликатуры', () => {
  // C-dur: x32010 → C3 E3 G3 C4 E4 (струны 1..5), 6-я (E2) заглушена.
  const expected = [
    { string: 0, midi: null, openMidi: 40 },
    { string: 1, midi: 48, openMidi: 45 },
    { string: 2, midi: 52, openMidi: 50 },
    { string: 3, midi: 55, openMidi: 55 },
    { string: 4, midi: 60, openMidi: 59 },
    { string: 5, midi: 64, openMidi: 64 },
  ];

  it('чистый аккорд — все струны в порядке', () => {
    const r = checkFingering(spectrum([48, 52, 55, 60, 64].map((midi) => ({ midi }))), expected);
    expect(r.good).toBe(6);
    expect(r.extras).toEqual([]);
  });

  it('приглушённая струна и лишняя нота находятся', () => {
    // Си-струна (C4) почти не звучит, а вместо неё звенит открытая B3.
    const r = checkFingering(
      spectrum([{ midi: 48 }, { midi: 52 }, { midi: 55 }, { midi: 60, amp: 0.02 }, { midi: 64 }, { midi: 59, amp: 0.8 }]),
      expected,
    );
    // B3 вместо C4 на второй струне — струна «не та».
    expect(r.strings[4].status).toBe('wrong');
    expect(r.strings[4].heard).toBe(59);
    expect(r.extras).toContain(59);
  });

  it('звон заглушенной басовой струны', () => {
    const r = checkFingering(
      spectrum([{ midi: 40, amp: 0.9 }, { midi: 48 }, { midi: 52 }, { midi: 55 }, { midi: 60 }, { midi: 64 }]),
      expected,
    );
    expect(r.strings[0].status).toBe('ringing');
  });
});

describe('подбор мелодии', () => {
  it('кадры высоты тона превращаются в ноты', () => {
    const t = new MelodyTracker();
    const feed = (midi: number | null, from: number, to: number) => {
      for (let x = from; x < to; x += 0.016) t.feed(midi, x);
    };
    feed(64, 0, 0.3);
    feed(null, 0.3, 0.45);
    feed(67, 0.45, 0.8);
    feed(69, 0.8, 1.0);
    t.flush();
    expect(t.notes.map((n) => n.midi)).toEqual([64, 67, 69]);
  });

  it('короткий «проскок» высоты не становится нотой', () => {
    const t = new MelodyTracker();
    for (let x = 0; x < 0.3; x += 0.016) t.feed(x > 0.1 && x < 0.13 ? 65 : 64, x);
    t.flush();
    expect(t.notes.map((n) => n.midi)).toEqual([64]);
  });

  it('удар сразу после начала ноты не удваивает её, а повторный удар — новая нота', () => {
    const t = new MelodyTracker();
    for (let x = 0; x < 0.6; x += 0.016) t.feed(64, x, Math.abs(x - 0.064) < 0.008 || Math.abs(x - 0.4) < 0.008);
    t.flush();
    expect(t.notes.map((n) => n.midi)).toEqual([64, 64]);
    expect(t.notes[1].start).toBeGreaterThan(0.35);
  });

  it('ноты раскладываются по струнам рядом друг с другом', () => {
    // E4 G4 A4 — на первой струне 0-3-5 или рядом.
    const pos = placeOnFretboard([64, 67, 69], STD);
    expect(pos.every((p) => p != null && p.fret <= 5)).toBe(true);
    const tab = melodyTab([64, 67, 69], STD);
    expect(tab.split('\n')).toHaveLength(6);
    expect(tab.split('\n')[0].startsWith('E|')).toBe(true);
  });
});

describe('ритм', () => {
  const beats = [0, 0.5, 1, 1.5];
  it('ошибка относительно ближайшей доли', () => {
    expect(beatError(0.52, beats, 0.5)).toBeCloseTo(0.02);
    expect(beatError(0.97, beats, 0.5)).toBeCloseTo(-0.03);
    expect(beatError(0.26, beats, 0.5, 2)).toBeCloseTo(0.01);
  });
  it('итог: смещение и разброс', () => {
    const s = timingSummary([0.02, 0.02, -0.02, -0.02])!;
    expect(s.mean).toBe(0);
    expect(s.spread).toBe(20);
    expect(s.accuracy).toBe(20);
  });
});

describe('статистика занятий', () => {
  const today = new Date(2026, 8, 30);
  const days = {
    '2026-09-30': { seconds: 600, chords: ['Am'] },
    '2026-09-29': { seconds: 120, chords: [] },
    '2026-09-28': { seconds: 300, chords: [] },
    '2026-09-26': { seconds: 900, chords: [] },
  };
  it('серия дней подряд', () => {
    expect(streak(days, today)).toBe(3);
    // Сегодня ещё не занимались — серия считается до вчера.
    expect(streak({ ...days, '2026-09-30': { seconds: 0, chords: [] } }, today)).toBe(2);
  });
  it('последние дни и итог', () => {
    const last = lastDays(days, 5, today);
    expect(last.map((d) => d.minutes)).toEqual([15, 0, 5, 2, 10]);
    expect(totalMinutes(days)).toBe(32);
  });
});

describe('совпадение аккорда в упражнениях', () => {
  it('тоника и лад должны совпасть, септима — не обязательна', () => {
    expect(matchesChord('Am', { rootPc: 9, templateId: 'min' })).toBe(true);
    expect(matchesChord('Am', { rootPc: 9, templateId: 'm7' })).toBe(true);
    expect(matchesChord('Am', { rootPc: 9, templateId: 'maj' })).toBe(false);
    expect(matchesChord('G', { rootPc: 7, templateId: '7' })).toBe(true);
    expect(matchesChord('G', { rootPc: 0, templateId: 'maj' })).toBe(false);
  });
});

describe('ритм: оценка удара', () => {
  it('в долю, чуть, мимо и серия', async () => {
    const { classifyHit, hitStreak, timingAdvice, timingSummary } = await import('../src/core/practice/timing');
    expect(classifyHit(0.01).zone).toBe('ok');
    expect(classifyHit(-0.05)).toEqual({ zone: 'near', text: 'Чуть рано (−50 мс)' });
    expect(classifyHit(0.1).text).toBe('Поздно! (+100 мс)');
    expect(hitStreak([0.2, 0.01, -0.02, 0.005])).toBe(3);
    expect(timingAdvice(timingSummary([-0.05, -0.04, -0.06, -0.05])!).tip).toContain('спешите');
  });
});
