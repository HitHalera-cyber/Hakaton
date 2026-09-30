// Шина событий между модулями: модули не импортируют друг друга, а публикуют и слушают события.

import type { RecognizedChord } from '../core/analysis/chordRecognition';
import type { HeardNotes } from '../core/analysis/liveSound';

export interface BusEvents {
  /** Аккорд услышан с гитары (микрофон). */
  'chord:heard': RecognizedChord;
  /** С гитары слышна одна нота или интервал (две ноты). */
  'notes:heard': HeardNotes;
  /** Удар по струнам (резкий рост громкости) — время по часам AudioContext. */
  'mic:onset': { time: number; level: number };
  /** Щелчок метронома прозвучал (время по часам AudioContext). */
  'metronome:beat': { time: number; beat: number };
}

type Handler<K extends keyof BusEvents> = (payload: BusEvents[K]) => void;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const handlers = new Map<keyof BusEvents, Set<(payload: any) => void>>();

export const bus = {
  on<K extends keyof BusEvents>(event: K, fn: Handler<K>): () => void {
    let set = handlers.get(event);
    if (!set) handlers.set(event, (set = new Set()));
    set.add(fn);
    return () => void set.delete(fn);
  },
  emit<K extends keyof BusEvents>(event: K, payload: BusEvents[K]) {
    handlers.get(event)?.forEach((fn) => fn(payload));
  },
};
