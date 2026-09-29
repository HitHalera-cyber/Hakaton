import { describe, expect, it } from 'vitest';
import { CHORD_TEMPLATES, detectChord } from '../src/music/chords';
import { parseChordSymbol } from '../src/music/chordParse';
import { computeFingering, fingerKey } from '../src/music/fingering';
import { applyCapo, boardFromFrets, boardFromMidi, emptyBoard, soundingNotes, toggleFret, transposeBoard } from '../src/music/fretboard';
import { detectPitch, freqToMidi } from '../src/music/pitch';
import { SCALES, keyChords, progressionChords, PROGRESSIONS, scaleNoteNames } from '../src/music/scales';
import { TUNINGS } from '../src/music/tunings';
import { fretsToString, generateVoicings } from '../src/music/voicings';
import { writeMidiFile } from '../src/midi/midiFile';

const STD = TUNINGS.standard.strings;
const tpl = (id: string) => CHORD_TEMPLATES.find((t) => t.id === id)!;
const tab = (s: string) => [...s].map((c) => (c === 'x' ? null : parseInt(c, 16)));

describe('разбор названий аккордов', () => {
  const cases: [string, string][] = [
    ['C', 'C'], ['Am', 'Am'], ['Cmaj7', 'Cmaj7'], ['CM7', 'Cmaj7'], ['CΔ', 'Cmaj7'], ['Dm/F', 'Dm/F'],
    ['F#m7b5', 'F#m7b5'], ['Bø', 'Bm7b5'], ['Bb', 'Bb'], ['Asus', 'Asus4'], ['G°7', 'Gdim7'], ['E+', 'Eaug'],
    ['c#min7', 'C#m7'], ['D6/9', 'D6/9'], ['Ebadd9', 'Ebadd9'], ['G7sus', 'G7sus4'], ['A♭m', 'Abm'],
  ];
  for (const [input, symbol] of cases) it(`${input} → ${symbol}`, () => expect(parseChordSymbol(input)?.symbol).toBe(symbol));
  it('ерунда не разбирается', () => {
    expect(parseChordSymbol('H7')).toBeNull();
    expect(parseChordSymbol('Cxyz')).toBeNull();
    expect(parseChordSymbol('')).toBeNull();
  });
});

describe('генератор аппликатур', () => {
  const has = (rootPc: number, id: string, shape: string, tuning = STD) =>
    generateVoicings(rootPc, tpl(id), tuning, { limit: 30 }).map((v) => fretsToString(v.frets)).includes(shape);
  it('C — открытая x32010', () => expect(has(0, 'maj', 'x32010')).toBe(true));
  it('G — открытая 320003 или 320033', () => expect(has(7, 'maj', '320003') || has(7, 'maj', '320033')).toBe(true));
  it('F — баррэ 133211', () => expect(has(5, 'maj', '133211')).toBe(true));
  it('Am — x02210', () => expect(has(9, 'min', 'x02210')).toBe(true));
  it('E7 — 020100', () => expect(has(4, '7', '020100')).toBe(true));
  it('все аппликатуры звучат как нужный аккорд, бас — тоника', () => {
    for (const id of ['maj', 'min', '7', 'maj7', 'm7', 'sus4', 'dim7', 'add9']) {
      for (let root = 0; root < 12; root++) {
        const list = generateVoicings(root, tpl(id), STD);
        expect(list.length).toBeGreaterThan(0);
        for (const v of list) {
          const notes = soundingNotes(boardFromFrets(v.frets), STD).map((n) => n.midi);
          const r = detectChord(notes);
          expect(r.kind).toBe('chord');
          expect(r.bassPc).toBe(root);
          expect(computeFingering(boardFromFrets(v.frets)).count).toBeLessThanOrEqual(4);
        }
      }
    }
  });
  it('работает для укулеле и 7-струнной', () => {
    expect(has(0, 'maj', '0003', TUNINGS.ukulele.strings)).toBe(true); // строй re-entrant: самая низкая нота — C
    expect(generateVoicings(7, tpl('maj'), TUNINGS.seven.strings).length).toBeGreaterThan(3);
  });
});

describe('пальцы', () => {
  it('C x32010: 3-2-1', () => {
    const f = computeFingering(boardFromFrets(tab('x32010')));
    expect(f.fingers.get(fingerKey(1, 3))).toBe(3);
    expect(f.fingers.get(fingerKey(2, 2))).toBe(2);
    expect(f.fingers.get(fingerKey(4, 1))).toBe(1);
    expect(f.barre).toBeNull();
    expect(f.warnings).toEqual([]);
  });
  it('F 133211: баррэ на 1 ладу', () => {
    const f = computeFingering(boardFromFrets(tab('133211')));
    expect(f.barre).toEqual({ fret: 1, fromString: 0, toString: 5 });
    expect(f.count).toBe(4);
    expect(f.fingers.get(fingerKey(3, 2))).toBe(2);
  });
  it('неиграбельная растяжка', () => {
    const f = computeFingering(boardFromFrets([1, null, null, null, null, 8]));
    expect(f.warnings.join()).toContain('растяжка');
  });
});

describe('каподастр и транспонирование', () => {
  it('каподастр: открытая струна звучит на ладу capo, точки под ним убираются', () => {
    let b = boardFromFrets(tab('x32010'));
    const shifted = transposeBoard(b, 2, 0)!;
    expect(fretsToString(shifted.map((s) => (s.muted ? null : s.frets[0] ?? (s.open ? 0 : null))))).toBe('x54232');
    b = boardFromFrets([null, 5, 4, 2, 3, 2], 2);
    expect(detectChord(soundingNotes(b, STD, 2).map((n) => n.midi)).primary!.symbol).toBe('D');
    expect(applyCapo(toggleFret(emptyBoard(), 0, 1), 2)[0].frets).toEqual([]);
  });
  it('транспонирование за пределы грифа запрещено', () => {
    expect(transposeBoard(boardFromFrets(tab('x32010')), -1)).toBeNull();
  });
  it('раскладка MIDI с каподастром', () => {
    const notes = [50, 57, 62, 66];
    const b = boardFromMidi(notes, STD, 2);
    expect(soundingNotes(b, STD, 2).map((n) => n.midi)).toEqual(notes);
  });
});

describe('гаммы и тональности', () => {
  it('ноты гамм написаны по ступеням', () => {
    expect(scaleNoteNames(5, SCALES[0]).join(' ')).toBe('F G A Bb C D E');
    expect(scaleNoteNames(9, SCALES[1]).join(' ')).toBe('A B C D E F G');
  });
  it('аккорды тональности', () => {
    expect(keyChords(7, 'major', false).map((c) => c.symbol).join(' ')).toBe('G Am Bm C D Em F#dim');
    expect(keyChords(0, 'major', true).map((c) => c.symbol).join(' ')).toBe('Cmaj7 Dm7 Em7 Fmaj7 G7 Am7 Bm7b5');
    expect(keyChords(9, 'minor', false).map((c) => c.roman).join(' ')).toBe('i ii° III iv v VI VII');
  });
  it('последовательности', () => {
    const pop = PROGRESSIONS.find((p) => p.id === 'pop')!;
    expect(progressionChords(0, 'major', pop).map((c) => c.symbol).join(' ')).toBe('C G Am F');
    const and = PROGRESSIONS.find((p) => p.id === 'andalusian')!;
    expect(progressionChords(9, 'minor', and).map((c) => c.symbol).join(' ')).toBe('Am G F E');
    const blues = PROGRESSIONS.find((p) => p.id === 'blues')!;
    expect(progressionChords(9, 'major', blues).slice(0, 5).map((c) => c.symbol).join(' ')).toBe('A7 A7 A7 A7 D7');
  });
});

describe('тюнер', () => {
  const sr = 44100;
  const tone = (f: number, harmonics = 5) => {
    const x = new Float32Array(4096);
    for (let i = 0; i < x.length; i++) for (let h = 1; h <= harmonics; h++) x[i] += (0.3 / h) * Math.sin((2 * Math.PI * f * h * i) / sr);
    return x;
  };
  for (const f of [82.41, 110, 146.83, 196, 246.94, 329.63, 41.2]) {
    it(`${f} Гц`, () => {
      const r = detectPitch(tone(f), sr)!;
      expect(Math.abs(1200 * Math.log2(r.freq / f))).toBeLessThan(3);
    });
  }
  it('тишина — нет тона', () => expect(detectPitch(new Float32Array(4096), sr)).toBeNull());
  it('частота → MIDI', () => expect(Math.round(freqToMidi(440))).toBe(69));
});

describe('MIDI-файл', () => {
  it('корректный заголовок и конец трека', () => {
    const bytes = writeMidiFile([{ midi: 60, start: 0, duration: 1, velocity: 0.8 }], 120, 25);
    expect(String.fromCharCode(...bytes.slice(0, 4))).toBe('MThd');
    expect(String.fromCharCode(...bytes.slice(14, 18))).toBe('MTrk');
    expect([...bytes.slice(-3)]).toEqual([0xff, 0x2f, 0x00]);
  });
});
