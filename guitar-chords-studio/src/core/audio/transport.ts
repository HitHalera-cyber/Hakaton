// Планировщик ритма: точно расставляет события по времени AudioContext с упреждением
// (классическая схема «lookahead»): таймер раз в 25 мс планирует всё, что попадает в ближайшие 120 мс.

import { audio } from './engine';

export type StepCallback = (step: number, time: number) => void;

export class Transport {
  private timer: number | null = null;
  private nextTime = 0;
  private step = 0;
  bpm = 100;
  /** Сколько шагов на долю (2 — восьмые). */
  stepsPerBeat = 2;

  constructor(private onStep: StepCallback) {}

  get running(): boolean {
    return this.timer != null;
  }

  get stepDuration(): number {
    return 60 / this.bpm / this.stepsPerBeat;
  }

  start(bpm: number, stepsPerBeat = 2) {
    this.stop();
    this.bpm = bpm;
    this.stepsPerBeat = stepsPerBeat;
    this.step = 0;
    this.nextTime = audio.now + 0.08;
    this.timer = window.setInterval(() => this.tick(), 25);
    this.tick();
  }

  private tick() {
    const horizon = audio.now + 0.12;
    while (this.nextTime < horizon) {
      this.onStep(this.step, this.nextTime);
      this.step++;
      this.nextTime += this.stepDuration;
    }
  }

  stop() {
    if (this.timer != null) window.clearInterval(this.timer);
    this.timer = null;
  }
}

/** Выполнить колбэк в момент звучания события (для подсветки в интерфейсе). */
export function atAudioTime(time: number, fn: () => void) {
  const delay = Math.max(0, (time - audio.now) * 1000);
  window.setTimeout(fn, delay);
}
