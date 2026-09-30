// Проигрывание последовательности аккордов по выбранной схеме боя.

import { audio, type ChordNote } from '../core/audio/engine';
import { PATTERNS, playPatternStep } from '../core/audio/patterns';
import { Transport, atAudioTime } from '../core/audio/transport';
import { soundingNotes } from '../core/music/fretboard';
import type { SeqItem } from '../store/model';
import { store } from '../store';

export function itemNotes(item: SeqItem): ChordNote[] {
  return soundingNotes(item.board, item.strings, item.capo).map((n) => ({ midi: n.midi, string: n.string }));
}

class SequencerService {
  private list: SeqItem[] = [];
  private transport = new Transport((step, time) => {
    const list = this.list;
    const r = store.getState().settings.rhythm;
    const stepsOf = (it: SeqItem) => Math.max(1, Math.round(it.beats * 2));
    const total = list.reduce((a, it) => a + stepsOf(it), 0);
    if (total === 0) return;
    if (!r.loop && step >= total) {
      this.transport.stop();
      atAudioTime(time, () => store.getState().setSeq({ playing: false, current: null }));
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
    playPatternStep(pattern, itemNotes(item), step % 8, s === 0, time, this.transport.stepDuration);
    if (r.click && step % 2 === 0) audio.click(time, (step / 2) % r.meter === 0);
    if (s === 0) {
      atAudioTime(time, () => {
        const st = store.getState();
        const i = st.sequence.indexOf(item);
        st.setSeq({ current: i >= 0 ? i : null });
        // Аккорд последовательности — на гриф (если совпадает число струн).
        if (item.strings.length === st.guitar().strings.length) st.setBoard(item.board);
      });
    }
  });

  constructor() {
    store.subscribe((s, prev) => {
      if (s.settings.rhythm.bpm !== prev.settings.rhythm.bpm) this.transport.bpm = s.settings.rhythm.bpm;
    });
  }

  play(override?: SeqItem[]) {
    const list = override ?? store.getState().sequence;
    if (!list.length) return;
    this.list = list;
    audio.stopAll(0.03);
    this.transport.start(store.getState().settings.rhythm.bpm, 2);
    store.getState().setSeq({ playing: true });
  }

  stop() {
    this.transport.stop();
    audio.stopAll();
    store.getState().setSeq({ playing: false, current: null });
  }
}

export const sequencer = new SequencerService();
