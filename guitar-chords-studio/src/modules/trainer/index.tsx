import { emptyBoard } from '../../core/music/fretboard';
import { boardInput } from '../../services/boardInput';
import { store, useGuitar } from '../../store';
import type { ModuleDef } from '../types';
import { TrainerPanel } from './TrainerPanel';

function TrainerView() {
  const g = useGuitar();
  return (
    <TrainerPanel
      tuning={g.strings}
      capo={g.capo}
      soundingMidis={g.boardNotes.map((n) => n.midi)}
      registerCellHandler={(fn) => {
        boardInput.register(fn);
        if (!fn) store.getState().setFlash(null);
      }}
      setFlash={(f) => store.getState().setFlash(f)}
      loadFrets={(frets) => store.getState().loadFrets(frets)}
      clearBoard={() => store.getState().setBoard(emptyBoard(g.strings.length))}
    />
  );
}

export const trainerModule: ModuleDef = {
  id: 'trainer',
  title: 'Тренажёр',
  icon: '🎯',
  group: 'practice',
  description: 'Найди ноту на грифе, построй аккорд, угадай аккорд или ноту на слух',
  keywords: ['ноты', 'слух', 'упражнения'],
  View: TrainerView,
};
