// Высота тона с общего микрофона — для тюнера и подбора мелодии.

import { useEffect, useRef, useState } from 'react';
import { detectPitch, freqToMidi } from '../core/analysis/pitch';
import { mic, rmsOf } from './mic';

export interface PitchReading {
  freq: number;
  /** Ближайшая нота (MIDI). */
  midi: number;
  cents: number;
  /** Надёжность 0..1. */
  clarity: number;
}

/** Покадровое определение высоты тона. onFrame вызывается на каждом кадре (для подбора мелодии). */
/** onFrame получает громкость по последним ~20 мс — по ней удобно ловить удары по струнам. */
export function usePitch(onFrame?: (r: PitchReading | null, level: number, time: number) => void) {
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [reading, setReading] = useState<PitchReading | null>(null);
  const [level, setLevel] = useState(0);
  const raf = useRef<number | null>(null);
  const history = useRef<number[]>([]);
  const frameCb = useRef(onFrame);
  frameCb.current = onFrame;

  const stop = () => {
    if (raf.current == null) return;
    cancelAnimationFrame(raf.current);
    raf.current = null;
    mic.release();
    setActive(false);
    setReading(null);
    setLevel(0);
  };
  useEffect(() => stop, []);

  const start = async () => {
    setError('');
    try {
      await mic.acquire();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setActive(true);
    const buf = new Float32Array(4096);
    const tick = () => {
      if (!mic.read(buf)) return;
      const rms = rmsOf(buf, buf.length);
      const lvl = Math.min(1, rms * 8);
      setLevel(lvl);
      const r = detectPitch(buf, mic.sampleRate);
      let out: PitchReading | null = null;
      if (r && r.clarity > 0.8) {
        history.current = [...history.current, r.freq].slice(-5);
        const sorted = [...history.current].sort((a, b) => a - b);
        const f = sorted[Math.floor(sorted.length / 2)];
        const m = freqToMidi(f);
        const midi = Math.round(m);
        out = { freq: f, midi, cents: Math.round((m - midi) * 100), clarity: r.clarity };
        setReading(out);
      } else history.current = [];
      frameCb.current?.(out, rmsOf(buf, 1024), mic.now);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  return { active, error, reading, level, start: () => void start(), stop };
}
