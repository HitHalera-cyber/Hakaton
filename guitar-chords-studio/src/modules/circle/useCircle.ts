import { cellChord, circlePosition, type CirclePos } from '../../core/music/circle';
import { store, usePick } from '../../store';
import { resolveKey } from './CirclePanel';

/** Поставить на гриф аккорд из ячейки круга. */
export function pickCircle(pos: CirclePos) {
  const c = cellChord(pos);
  const s = store.getState();
  const frets = s.voicingFor(c.rootPc, c.templateId);
  if (frets) s.loadFrets(frets);
}

/** Данные для компактного круга (в «Слушать», в раскладке «Слушатель», в плитках). */
export function useCircleProps() {
  const { trail, circleKey } = usePick((s) => ({ trail: s.trail, circleKey: s.settings.view.circleKey }));
  return {
    active: trail[0] ? circlePosition(trail[0].rootPc, trail[0].templateId) : null,
    pulseKey: trail[0]?.id,
    trail: trail.slice(1, 4).map((c) => circlePosition(c.rootPc, c.templateId)),
    keySel: resolveKey(circleKey, trail).key,
    onPick: pickCircle,
  };
}
