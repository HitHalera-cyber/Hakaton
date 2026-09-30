import { describe, expect, it } from 'vitest';
import { detectChord } from '../src/core/music/chords';
import { boardFromMidi, emptyBoard, soundingNotes, toggleFret, cycleNut, setNut } from '../src/core/music/fretboard';
import { TUNINGS } from '../src/core/music/tunings';

const STD = TUNINGS.standard.strings;

/** Аппликатура в табулатурной записи от 6-й к 1-й струне: 'x32010'. */
function shape(tab: string, tuning = STD): number[] {
  const out: number[] = [];
  [...tab].forEach((ch, i) => {
    if (ch === 'x') return;
    out.push(tuning[i] + parseInt(ch, 16));
  });
  return out;
}

const cases: [string, string, string, string][] = [
  ['x32010', 'C', 'До мажор', 'C E G'],
  ['x02210', 'Am', 'Ля минор', 'A C E'],
  ['320001', 'G7', 'Соль мажорный септаккорд', 'G B D F'],
  ['xx3210', 'Fmaj7', 'Фа большой мажорный септаккорд', 'F A C E'],
  ['022030', 'Em7', 'Ми минорный септаккорд', 'E G B D'],
  ['244222', 'F#m', 'Фа-диез минор', 'F# A C#'],
  ['x13331', 'Bb', 'Си-бемоль мажор', 'Bb D F'],
  ['3x443x', 'Gmaj7', 'Соль большой мажорный септаккорд', 'G B D F#'],
  ['x32030', 'Cadd9', 'До мажор с добавленной ноной', 'C E G D'],
  ['xx0231', 'Dm', 'Ре минор', 'D F A'],
  ['xx0212', 'D7', 'Ре мажорный септаккорд', 'D F# A C'],
  ['x2323x', 'Bm7b5', 'Си полууменьшённый септаккорд', 'B D F A'],
  ['x02200', 'Asus2', 'Ля с задержанием секунды (sus2)', 'A B E'],
  ['xx0233', 'Dsus4', 'Ре с задержанием кварты (sus4)', 'D G A'],
  ['022xxx', 'E5', 'Ми квинтаккорд (пауэр-аккорд)', 'E B'],
  ['x46654', 'C#m', 'До-диез минор', 'C# E G#'],
  ['466444', 'G#m', 'Соль-диез минор', 'G# B D#'],
  ['x35353', 'C7', 'До мажорный септаккорд', 'C E G Bb'],
  ['x32310', 'C7', 'До мажорный септаккорд', 'C E Bb'],
  ['5x454x', 'Adim7', 'Ля уменьшённый септаккорд', 'A C Eb Gb'],
];

describe('detectChord — типичные аппликатуры', () => {
  for (const [tab, symbol, ru, notes] of cases) {
    it(`${tab} → ${symbol}`, () => {
      const r = detectChord(shape(tab));
      expect(r.kind).toBe('chord');
      expect(r.primary!.symbol).toBe(symbol);
      expect(r.primary!.nameRu).toBe(ru);
      expect(r.noteNames.join(' ')).toBe(notes);
    });
  }
});

describe('обращения', () => {
  it('C с басом E — секстаккорд', () => {
    const r = detectChord(shape('032010'));
    expect(r.primary!.symbol).toBe('C/E');
    expect(r.primary!.inversionRu).toBe('бас Ми — секстаккорд (1-е обращение)');
  });
  it('C с басом G — квартсекстаккорд', () => {
    const r = detectChord(shape('332010'));
    expect(r.primary!.symbol).toBe('C/G');
    expect(r.primary!.inversionRu).toContain('квартсекстаккорд');
  });
  it('разные аппликатуры одного аккорда дают одно название', () => {
    for (const tab of ['320003', '355433', 'xx5433', '3x0003']) {
      expect(detectChord(shape(tab)).primary!.symbol).toBe('G');
    }
  });
  it('C6 и Am7 различаются басом', () => {
    expect(detectChord([48, 52, 55, 57]).primary!.symbol).toBe('C6');
    expect(detectChord([45, 48, 52, 55]).primary!.symbol).toBe('Am7');
  });
  it('Am/C, а не C6 без квинты', () => {
    expect(detectChord([48, 52, 57]).primary!.symbol).toBe('Am/C');
  });
});

describe('особые случаи', () => {
  it('пусто', () => expect(detectChord([]).kind).toBe('empty'));
  it('одна нота', () => expect(detectChord([60, 72]).kind).toBe('note'));
  it('интервал', () => {
    const r = detectChord([60, 64]);
    expect(r.kind).toBe('interval');
    expect(r.intervalRu).toBe('большая терция');
    expect(r.alternatives[0].symbol).toBe('C(no5)');
  });
  it('неизвестный аккорд с ближайшими вариантами', () => {
    const r = detectChord([60, 61, 64, 67]);
    expect(r.kind).toBe('unknown');
    expect(r.alternatives.map((a) => a.symbol)).toContain('C(+C#)');
  });
  it('кластер без вариантов', () => {
    const r = detectChord([60, 61, 62, 63]);
    expect(r.kind).toBe('unknown');
  });
});

describe('модель грифа', () => {
  it('точки, открытые и заглушённые струны', () => {
    let b = emptyBoard();
    b = toggleFret(b, 1, 3);
    b = toggleFret(b, 2, 2);
    b = cycleNut(b, 3); // G открыта
    b = toggleFret(b, 4, 1);
    b = cycleNut(b, 5); // e открыта
    b = setNut(b, 0, 'muted'); // 6-я заглушена
    b = cycleNut(b, 1);
    b = cycleNut(b, 1); // открыли и снова убрали — A не звучит открытой
    expect(detectChord(soundingNotes(b, STD).map((n) => n.midi)).primary!.symbol).toBe('C');
  });
  it('раскладка MIDI-аккорда на гриф сохраняет звучание', () => {
    const notes = [48, 52, 55, 60, 64];
    const b = boardFromMidi(notes, STD);
    expect(
      soundingNotes(b, STD)
        .map((n) => n.midi)
        .sort(),
    ).toEqual(notes.sort());
  });
  it('Drop D меняет басовую струну', () => {
    const r = detectChord(shape('000232', TUNINGS.dropD.strings));
    expect(r.primary!.symbol).toBe('D');
  });
});

describe('варианты', () => {
  it('у точного аккорда — только точные альтернативные трактовки', () => {
    const r = detectChord([48, 52, 55, 57]);
    expect(r.alternatives.map((a) => a.symbol)).toEqual(['Am7/C']);
  });
  it('нет бессмысленных вариантов без характерной ступени', () => {
    const r = detectChord([60, 61, 64, 67]);
    for (const a of r.alternatives) expect(a.symbol).not.toMatch(/no(7|9|11|13|6)/);
  });
});
