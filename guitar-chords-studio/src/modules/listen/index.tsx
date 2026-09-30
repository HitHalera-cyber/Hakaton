import { CircleOfFifths } from '../../ui/CircleOfFifths';
import { store, useGuitar } from '../../store';
import { useCircleProps } from '../circle/useCircle';
import type { ModuleDef } from '../types';
import { ListenPanel } from './ListenPanel';
import { useListener } from './useListener';

function ListenView() {
  const listener = useListener();
  const g = useGuitar();
  const circle = useCircleProps();
  return (
    <ListenPanel
      listener={listener}
      onPick={(c) => store.getState().showChord(c.rootPc, c.templateId, c.bassPc)}
      voicing={(c) => store.getState().voicingFor(c.rootPc, c.templateId, c.bassPc)}
      capo={g.capo}
      circle={<CircleOfFifths compact size={230} {...circle} />}
    />
  );
}

export const listenModule: ModuleDef = {
  id: 'listen',
  title: 'Слушать гитару',
  icon: '👂',
  group: 'recognize',
  description: 'Сыграйте аккорд — программа назовёт его и покажет на грифе',
  keywords: ['микрофон', 'распознать', 'аккорд на слух'],
  View: ListenView,
};
