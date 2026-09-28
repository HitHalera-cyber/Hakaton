import { useCallback, useEffect, useRef, useState } from 'react';
import { audio, type ChordNote } from '../audio/engine';
import { PATTERNS, playPatternStep } from '../audio/patterns';
import { Transport, atAudioTime } from '../audio/transport';
import { soundingNotes, type Board } from '../music/fretboard';

export interface SeqItem {
  id: string;
  symbol: string;
  board: Board;
  strings: number[];
  capo: number;
  /** Длительность в долях (четвертях). */
  beats: number;
}

export interface RhythmSettings {
  bpm: number;
  patternId: string;
  loop: boolean;
  click: boolean;
  /** Метроном: долей в такте. */
  meter: number;
  accent: boolean;
}

export const DEFAULT_RHYTHM: RhythmSettings = { bpm: 90, patternId: 'six', loop: true, click: false, meter: 4, accent: true };

export function itemNotes(item: SeqItem): ChordNote[] {
  return soundingNotes(item.board, item.strings, item.capo).map((n) => ({ midi: n.midi, string: n.string }));
}

/** Проигрывание последовательности аккордов по выбранной схеме боя. */
export function useSequencer(items: SeqItem[], rhythm: RhythmSettings, onChord: (item: SeqItem, index: number) => void) {
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const itemsRef = useRef(items);
  const rhythmRef = useRef(rhythm);
  const onChordRef = useRef(onChord);
  const listRef = useRef<SeqItem[]>(items);
  itemsRef.current = items;
  rhythmRef.current = rhythm;
  onChordRef.current = onChord;

  const transportRef = useRef<Transport | null>(null);
  if (!transportRef.current) {
    transportRef.current = new Transport((step, time) => {
      const list = listRef.current;
      const r = rhythmRef.current;
      const stepsOf = (it: SeqItem) => Math.max(1, Math.round(it.beats * 2));
      const total = list.reduce((a, it) => a + stepsOf(it), 0);
      if (total === 0) return;
      if (!r.loop && step >= total) {
        transportRef.current!.stop();
        atAudioTime(time, () => {
          setPlaying(false);
          setCurrent(null);
        });
        return;
      }
      let s = step % total;
      let idx = 0;
      while (s >= stepsOf(list[idx])) {
        s -= stepsOf(list[idx]);
        idx++;
      }
      const item = list[idx];
      const pattern = PATTERNS.find((p) => p.id === r.patternId) ?? PATTERNS[0];
      playPatternStep(pattern, itemNotes(item), step % 8, s === 0, time, transportRef.current!.stepDuration);
      if (r.click && step % 2 === 0) audio.click(time, (step / 2) % r.meter === 0);
      if (s === 0) {
        atAudioTime(time, () => {
          setCurrent(itemsRef.current.indexOf(item) >= 0 ? itemsRef.current.indexOf(item) : null);
          onChordRef.current(item, idx);
        });
      }
    });
  }

  // Темп меняется на лету.
  useEffect(() => {
    if (transportRef.current) transportRef.current.bpm = rhythm.bpm;
  }, [rhythm.bpm]);

  const play = useCallback((override?: SeqItem[]) => {
    const list = override ?? itemsRef.current;
    if (!list.length) return;
    listRef.current = list;
    audio.stopAll(0.03);
    transportRef.current!.start(rhythmRef.current.bpm, 2);
    setPlaying(true);
  }, []);

  const stop = useCallback(() => {
    transportRef.current!.stop();
    audio.stopAll();
    setPlaying(false);
    setCurrent(null);
  }, []);

  useEffect(() => () => transportRef.current?.stop(), []);

  return { playing, current, play, stop };
}
