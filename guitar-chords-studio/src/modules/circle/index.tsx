import { usePick } from '../../store';
import type { ModuleDef } from '../types';
import { CirclePanel } from './CirclePanel';
import { pickCircle } from './useCircle';

function CircleView() {
  const s = usePick((s) => ({
    trail: s.trail,
    circleKey: s.settings.view.circleKey,
    patchView: s.patchView,
    listening: s.listen.active,
    clearTrail: s.clearTrail,
  }));
  return (
    <CirclePanel
      trail={s.trail}
      keyChoice={s.circleKey}
      onKeyChoice={(circleKey) => s.patchView({ circleKey })}
      listening={s.listening}
      onPick={pickCircle}
      onClear={s.clearTrail}
    />
  );
}

export const circleModule: ModuleDef = {
  id: 'circle',
  title: 'Квинтовый круг',
  icon: '⭕',
  group: 'recognize',
  description: 'Круг квинт: светится аккорд, который звучит, и тональность',
  keywords: ['кварто-квинтовый', 'тональность', 'ступени'],
  View: CircleView,
};
