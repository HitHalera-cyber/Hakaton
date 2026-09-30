import { chordListener } from '../../services/chordListener';
import { usePick } from '../../store';

/** Состояние прослушивания гитары и управление им — для панелей. */
export function useListener() {
  const { listen, settings, patch } = usePick((s) => ({ listen: s.listen, settings: s.settings.listen, patch: s.patchListen }));
  return {
    ...listen,
    settings,
    patch,
    showOnBoard: settings.showOnBoard,
    start: () => void chordListener.start(),
    stop: () => chordListener.stop(),
    clearHistory: () => chordListener.clearHistory(),
  };
}

export type ChordListener = ReturnType<typeof useListener>;
