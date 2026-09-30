import { exportChord } from '../services/exports';
import { store, useGuitar } from '../store';
import { ChordDisplay } from '../ui/ChordDisplay';

/** Текущий аккорд: название, состав, кнопки «играть», «в избранное», экспорт. */
export function ChordCard() {
  const g = useGuitar();
  const st = store.getState();
  return (
    <ChordDisplay
      result={g.result}
      soundingMidi={g.activeMidi}
      source={g.source}
      capo={g.capo}
      shapeSymbol={g.shapeSymbol}
      warnings={g.source === 'board' ? g.fingering.warnings : []}
      onPlay={st.play}
      onSave={st.saveCurrent}
      onAddToSequence={st.addCurrentToSequence}
      onShowVoicings={g.chordRef ? () => st.showVoicings(g.chordRef!) : undefined}
      onExport={(k) => void exportChord(k)}
    />
  );
}
