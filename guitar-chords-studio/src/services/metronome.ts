// Метроном — общий для раздела «Метроном» и тренировки ритма. Каждая доля уходит в шину 'metronome:beat'.

import { audio } from '../core/audio/engine';
import { Transport, atAudioTime } from '../core/audio/transport';
import { store } from '../store';
import { bus } from './bus';

class MetronomeService {
  private transport = new Transport((step, time) => {
    const r = store.getState().settings.rhythm;
    const b = step % r.meter;
    audio.click(time, r.accent && b === 0);
    bus.emit('metronome:beat', { time, beat: b });
    atAudioTime(time, () => store.getState().setMetro({ beat: b }));
  });

  constructor() {
    store.subscribe((s, prev) => {
      if (s.settings.rhythm.bpm !== prev.settings.rhythm.bpm) this.transport.bpm = s.settings.rhythm.bpm;
    });
  }

  get running() {
    return this.transport.running;
  }

  /** Время начала следующей доли (для расчёта опережения/отставания). */
  get beatDuration() {
    return 60 / store.getState().settings.rhythm.bpm;
  }

  start() {
    this.transport.start(store.getState().settings.rhythm.bpm, 1);
    store.getState().setMetro({ running: true });
  }

  stop() {
    this.transport.stop();
    store.getState().setMetro({ running: false, beat: -1 });
  }

  toggle() {
    if (this.running) this.stop();
    else this.start();
  }
}

export const metronome = new MetronomeService();
