import { useGuitar } from '../../store';
import type { ModuleDef } from '../types';
import { TunerPanel } from './TunerPanel';

function TunerView() {
  const g = useGuitar();
  return <TunerPanel tuning={g.strings} capo={g.capo} />;
}

export const tunerModule: ModuleDef = {
  id: 'tuner',
  title: 'Тюнер',
  icon: '🎤',
  group: 'tools',
  description: 'Настройка гитары по микрофону',
  keywords: ['настроить', 'строй', 'микрофон'],
  View: TunerView,
};
