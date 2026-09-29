import { cycleNut, isBoardEmpty, setNut, toggleFret } from '../../core/music/fretboard';
import { pcName } from '../../core/music/notes';
import { SCALES, scaleDegrees } from '../../core/music/scales';
import { Fretboard } from '../../features/fretboard/Fretboard';
import { useApp } from '../AppContext';
import { scaleTitle } from '../panels';

/** Карточка с грифом: подсказка, гамма, «очистить» и сам гриф. */
export function BoardCard() {
  const { settings, guitar, midi } = useApp();
  const { view, scale, patchScale } = settings;
  const { board, result, capo } = guitar;
  const scaleDef = SCALES.find((s) => s.id === scale.scaleId) ?? SCALES[0];
  const trainerActive = view.tab === 'trainer' && guitar.cellHandler.current != null;

  return (
    <section className="panel board-panel">
      <div className="board-head">
        <span className="hint">
          {trainerActive
            ? 'Сейчас клики по грифу проверяет тренажёр'
            : 'Клик — поставить/убрать точку · у порожка: O → X → пусто · правый клик — заглушить струну'}
        </span>
        <div className="row">
          {scale.show && (
            <button className="btn small toggle on" onClick={() => patchScale({ show: false })} title="Скрыть гамму">
              Гамма: {pcName(scale.rootPc)} {scaleTitle(scale.scaleId)} ✕
            </button>
          )}
          <button
            className="btn danger small"
            onClick={guitar.clear}
            disabled={isBoardEmpty(board) && midi.active.size === 0}
            title="Delete"
          >
            ✕ Очистить
          </button>
        </div>
      </div>
      <Fretboard
        board={board}
        tuning={guitar.strings}
        capo={capo}
        showNotes={view.showNotes}
        dotLabel={view.dotLabel}
        midiNotes={midi.active}
        degreeByPc={result.primary?.degreeByPc}
        rootPc={result.kind === 'chord' ? result.primary?.rootPc : undefined}
        fingering={guitar.fingering}
        scale={scale.show ? { rootPc: scale.rootPc, degrees: scaleDegrees(scale.rootPc, scaleDef) } : null}
        flash={guitar.flash}
        onToggleFret={(s, f) => {
          if (guitar.cellHandler.current?.(s, f)) return;
          guitar.edit(toggleFret(board, s, f));
        }}
        onCycleNut={(s) => {
          if (guitar.cellHandler.current?.(s, capo)) return;
          guitar.edit(cycleNut(board, s));
        }}
        onMuteString={(s) => guitar.edit(setNut(board, s, board[s].muted ? 'none' : 'muted'))}
      />
    </section>
  );
}
