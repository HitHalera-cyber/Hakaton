import { useSyncExternalStore } from 'react';
import { cycleNut, isBoardEmpty, setNut, toggleFret } from '../core/music/fretboard';
import { pcName } from '../core/music/notes';
import { SCALES, scaleDegrees } from '../core/music/scales';
import { boardInput } from '../services/boardInput';
import { store, useGuitar, usePick } from '../store';
import { Fretboard } from '../ui/Fretboard';

/** Карточка с грифом: подсказка, гамма, «очистить» и сам гриф. */
export function BoardCard() {
  const s = usePick((s) => ({ view: s.settings.view, scale: s.settings.scale, board: s.board, flash: s.flash, patchScale: s.patchScale }));
  const g = useGuitar();
  const intercepted = useSyncExternalStore(boardInput.subscribe, () => boardInput.handler != null);
  const scaleDef = SCALES.find((x) => x.id === s.scale.scaleId) ?? SCALES[0];
  const st = store.getState();

  return (
    <section className="panel board-panel">
      <div className="board-head">
        <span className="hint">
          {intercepted
            ? 'Сейчас клики по грифу проверяет упражнение'
            : 'Клик — поставить/убрать точку · у порожка: O → X → пусто · правый клик — заглушить струну'}
        </span>
        <div className="row">
          {s.scale.show && (
            <button className="btn small toggle on" onClick={() => s.patchScale({ show: false })} title="Скрыть гамму">
              Гамма: {pcName(s.scale.rootPc)} {scaleDef.name.split(' (')[0].toLowerCase()} ✕
            </button>
          )}
          <button
            className="btn danger small"
            onClick={st.clearBoard}
            disabled={isBoardEmpty(s.board) && g.source === 'board'}
            title="Delete"
          >
            ✕ Очистить
          </button>
        </div>
      </div>
      <Fretboard
        board={s.board}
        tuning={g.strings}
        capo={g.capo}
        showNotes={s.view.showNotes}
        dotLabel={s.view.dotLabel}
        midiNotes={new Set(g.source === 'midi' ? g.activeMidi : [])}
        degreeByPc={g.result.primary?.degreeByPc}
        rootPc={g.result.kind === 'chord' ? g.result.primary?.rootPc : undefined}
        fingering={g.fingering}
        scale={s.scale.show ? { rootPc: s.scale.rootPc, degrees: scaleDegrees(s.scale.rootPc, scaleDef) } : null}
        flash={s.flash}
        onToggleFret={(str, f) => {
          if (boardInput.handler?.(str, f)) return;
          st.edit(toggleFret(store.getState().board, str, f));
        }}
        onCycleNut={(str) => {
          if (boardInput.handler?.(str, g.capo)) return;
          st.edit(cycleNut(store.getState().board, str));
        }}
        onMuteString={(str) => {
          const b = store.getState().board;
          st.edit(setNut(b, str, b[str].muted ? 'none' : 'muted'));
        }}
      />
    </section>
  );
}
