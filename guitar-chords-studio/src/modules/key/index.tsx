import { sequencer } from '../../services/sequencer';
import { store, useGuitar } from '../../store';
import type { ModuleDef } from '../types';
import { KeyPanel } from './KeyPanel';

function KeyView() {
  const g = useGuitar();
  return (
    <KeyPanel
      tuning={g.strings}
      capo={g.capo}
      onPick={(frets) => store.getState().loadFrets(frets)}
      onPlayProgression={(chords) => sequencer.play(store.getState().itemsFromFrets(chords))}
      onToSequence={(chords) => {
        const s = store.getState();
        s.setSequence(s.itemsFromFrets(chords));
        s.openModule('sequence');
      }}
    />
  );
}

export const keyModule: ModuleDef = {
  id: 'key',
  title: 'Тональность',
  icon: '🗝',
  group: 'learn',
  description: 'Аккорды тональности и популярные последовательности',
  keywords: ['прогрессия', 'ступени', 'мажор', 'минор'],
  View: KeyView,
};
