import { describe, expect, it } from 'vitest';
import { MAJOR_LABELS, MINOR_LABELS, cellChord, circlePosition, guessKey, inKey, keyName, romanInKey } from '../src/core/music/circle';

const pos = (rootPc: number, id: string) => circlePosition(rootPc, id);

describe('квинтовый круг', () => {
  it('мажор, минор и уменьшённые — на своих кольцах', () => {
    expect(pos(0, 'maj')).toEqual({ ring: 'major', index: 0 });
    expect(pos(7, '7')).toEqual({ ring: 'major', index: 1 }); // G7 — рядом с C
    expect(pos(5, 'maj7')).toEqual({ ring: 'major', index: 11 }); // Fmaj7
    expect(pos(9, 'min')).toEqual({ ring: 'minor', index: 0 }); // Am под C
    expect(pos(4, 'm7')).toEqual({ ring: 'minor', index: 1 }); // Em7 под G
    expect(pos(11, 'dim')).toEqual({ ring: 'dim', index: 0 }); // B° под C
    expect(pos(11, 'm7b5')).toEqual({ ring: 'dim', index: 0 });
  });
  it('подписи ячеек соответствуют аккордам', () => {
    for (let i = 0; i < 12; i++) {
      const maj = cellChord({ ring: 'major', index: i });
      const min = cellChord({ ring: 'minor', index: i });
      expect(circlePosition(maj.rootPc, 'maj').index).toBe(i);
      expect(circlePosition(min.rootPc, 'min').index).toBe(i);
    }
    expect(MAJOR_LABELS[3]).toBe('A');
    expect(MINOR_LABELS[3]).toBe('F#m');
  });
  it('аккорды тональности до мажор', () => {
    const key = { index: 0, mode: 'major' as const };
    const inC = ['maj:0', 'maj:5', 'maj:7', 'min:2', 'min:4', 'min:9', 'dim:11'].map((s) => {
      const [id, pc] = s.split(':');
      return inKey(pos(Number(pc), id), key);
    });
    expect(inC.every(Boolean)).toBe(true);
    expect(inKey(pos(2, 'maj'), key)).toBe(false); // D мажор — не в C
    expect(romanInKey(pos(7, 'maj'), key)).toBe('V');
    expect(romanInKey(pos(2, 'min'), key)).toBe('ii');
    expect(romanInKey(pos(11, 'dim'), key)).toBe('vii°');
  });
  it('угадывает тональность по аккордам', () => {
    const song = (list: [number, string][]) => list.map(([pc, id]) => pos(pc, id)).reverse();
    expect(
      keyName(
        guessKey(
          song([
            [0, 'maj'],
            [7, 'maj'],
            [9, 'min'],
            [5, 'maj'],
          ]),
        )!,
      ),
    ).toBe('C мажор');
    expect(
      keyName(
        guessKey(
          song([
            [9, 'min'],
            [5, 'maj'],
            [0, 'maj'],
            [7, 'maj'],
            [9, 'min'],
          ]),
        )!,
      ),
    ).toBe('A минор');
    expect(
      keyName(
        guessKey(
          song([
            [7, 'maj'],
            [2, 'maj'],
            [4, 'min'],
            [0, 'maj'],
          ]),
        )!,
      ),
    ).toBe('G мажор');
    expect(
      keyName(
        guessKey(
          song([
            [4, 'min'],
            [0, 'maj'],
            [7, 'maj'],
            [2, 'maj'],
            [4, 'min'],
          ]),
        )!,
      ),
    ).toBe('E минор');
    expect(guessKey([])).toBeNull();
  });
});
