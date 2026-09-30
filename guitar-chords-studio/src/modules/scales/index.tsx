import { audio } from '../../core/audio/engine';
import { store, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { ScalesPanel } from './ScalesPanel';

function ScalesView() {
  const { scale, patch } = usePick((s) => ({ scale: s.settings.scale, patch: s.patchScale }));
  return (
    <ScalesPanel
      settings={scale}
      onChange={patch}
      onPlay={(steps, rootPc) => {
        const g = store.getState().guitar();
        let start = Math.min(...g.strings) + g.capo;
        while (start % 12 !== rootPc) start++;
        const notes = [...steps.map((s) => start + s), start + 12];
        audio.stopAll(0.03);
        notes.forEach((m, i) => audio.playNote(m, 0.8, audio.now + i * 0.28, 'scale', 0.6));
      }}
    />
  );
}

export const scalesModule: ModuleDef = {
  id: 'scales',
  title: 'Гаммы',
  icon: '🎼',
  group: 'learn',
  description: 'Гаммы и лады на грифе: пентатоника, блюз, мажор, минор, лады',
  keywords: ['пентатоника', 'лад', 'импровизация', 'блюз'],
  View: ScalesView,
};
