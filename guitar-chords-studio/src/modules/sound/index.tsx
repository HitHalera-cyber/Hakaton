import { audio } from '../../core/audio/engine';
import { useGuitar, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { SoundPanel } from './SoundPanel';

function SoundView() {
  const { settings, patch } = usePick((s) => ({ settings: s.settings.sound, patch: s.patchSound }));
  const g = useGuitar();
  return <SoundPanel settings={settings} instrument={g.tuning.instrument} onChange={patch} onStop={() => audio.stopAll()} />;
}

export const soundModule: ModuleDef = {
  id: 'sound',
  title: 'Синтезация',
  icon: '🔊',
  group: 'modes',
  description: 'Бой, перебор, тембр гитары и громкость',
  keywords: ['тембр', 'громкость', 'бой', 'перебор', 'нейлон', 'электро'],
  View: SoundView,
};
