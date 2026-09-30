// Обработка звука песни: вырезание вокала и выделение баса.
// Вокал обычно стоит ровно по центру стерео, поэтому разность каналов (L − R) его убирает;
// бас тоже по центру — его возвращаем отдельно через фильтр низких частот.

import { audio } from '../../core/audio/engine';

export type SongFxMode = 'original' | 'novocal' | 'bass' | 'nobass';

export const FX_NAMES: Record<SongFxMode, string> = {
  original: 'Оригинал',
  novocal: 'Без вокала',
  bass: 'Только бас',
  nobass: 'Без баса',
};

const graphs = new WeakMap<HTMLMediaElement, Record<SongFxMode, GainNode>>();

/** Подключить элемент <audio> к обработке (один раз) и выбрать режим. */
export function setSongFx(el: HTMLMediaElement, mode: SongFxMode) {
  let outs = graphs.get(el);
  if (!outs) {
    const ctx = audio.context;
    const src = ctx.createMediaElementSource(el);
    const out = (): GainNode => {
      const g = ctx.createGain();
      g.gain.value = 0;
      g.connect(ctx.destination);
      return g;
    };
    outs = { original: out(), novocal: out(), bass: out(), nobass: out() };

    src.connect(outs.original);

    // Без вокала: (L − R) в оба канала + низкие частоты середины (бас и бочка остаются).
    const split = ctx.createChannelSplitter(2);
    src.connect(split);
    const left = ctx.createGain();
    const right = ctx.createGain();
    right.gain.value = -1;
    split.connect(left, 0);
    split.connect(right, 1);
    const side = ctx.createGain();
    left.connect(side);
    right.connect(side);
    const mid = ctx.createGain();
    mid.gain.value = 0.5;
    split.connect(mid, 0);
    split.connect(mid, 1);
    const midLow = ctx.createBiquadFilter();
    midLow.type = 'lowpass';
    midLow.frequency.value = 160;
    mid.connect(midLow);
    side.connect(outs.novocal);
    midLow.connect(outs.novocal);

    // Только бас: всё ниже ~250 Гц, чуть громче.
    const low = ctx.createBiquadFilter();
    low.type = 'lowpass';
    low.frequency.value = 250;
    low.Q.value = 0.8;
    const lowGain = ctx.createGain();
    lowGain.gain.value = 1.8;
    src.connect(low).connect(lowGain).connect(outs.bass);

    // Без баса: всё выше ~250 Гц.
    const high = ctx.createBiquadFilter();
    high.type = 'highpass';
    high.frequency.value = 250;
    src.connect(high).connect(outs.nobass);

    graphs.set(el, outs);
  }
  const now = audio.context.currentTime;
  for (const [m, g] of Object.entries(outs) as [SongFxMode, GainNode][]) g.gain.setTargetAtTime(m === mode ? 1 : 0, now, 0.02);
}
