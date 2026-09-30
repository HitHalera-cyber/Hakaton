import { exportSequence } from '../../services/exports';
import { sequencer } from '../../services/sequencer';
import { useGuitar, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { SequencerPanel } from './SequencerPanel';

function SequenceView() {
  const s = usePick((s) => ({
    items: s.sequence,
    rhythm: s.settings.rhythm,
    patchRhythm: s.patchRhythm,
    seq: s.seq,
    add: s.addCurrentToSequence,
    setSequence: s.setSequence,
    loadShape: s.loadShape,
    tuning: s.settings.view.tuning,
  }));
  const g = useGuitar();
  return (
    <SequencerPanel
      items={s.items}
      rhythm={s.rhythm}
      onRhythm={s.patchRhythm}
      playing={s.seq.playing}
      current={s.seq.current}
      canAdd={g.activeMidi.length > 0}
      onAdd={s.add}
      onChange={s.setSequence}
      onLoad={(it) => s.loadShape(it.board, s.tuning, it.strings, it.capo)}
      onPlay={() => sequencer.play()}
      onStop={() => sequencer.stop()}
      onExportMidi={() => void exportSequence(s.items, 'midi')}
      onExportTab={() => void exportSequence(s.items, 'tab')}
    />
  );
}

export const sequenceModule: ModuleDef = {
  id: 'sequence',
  title: 'Последовательность',
  icon: '🎵',
  group: 'play',
  description: 'Цепочка аккордов с боем, темпом и экспортом в MIDI и табулатуру',
  keywords: ['прогрессия', 'бой', 'шестёрка', 'midi', 'табулатура'],
  View: SequenceView,
};
