// След аккордов для квинтового круга: что звучит сейчас и что звучало перед этим —
// с грифа, MIDI-клавиатуры, гитары (микрофон) или разбираемой песни.

import { useCallback, useEffect, useRef, useState } from 'react';
import type { CircleChord } from '../features/circle/CirclePanel';
import type { Guitar } from './useGuitar';

export function useCircleTrail(guitar: Guitar) {
  const [trail, setTrail] = useState<CircleChord[]>([]);
  const id = useRef(0);

  const push = useCallback((c: Omit<CircleChord, 'id'>) => {
    setTrail((t) => (t[0]?.symbol === c.symbol ? t : [{ ...c, id: ++id.current }, ...t].slice(0, 12)));
  }, []);

  const { result, source } = guitar;
  useEffect(() => {
    if (result.kind !== 'chord' || !result.primary) return;
    const p = result.primary;
    push({ rootPc: p.rootPc, templateId: p.template.id, symbol: p.symbol, nameRu: p.nameRu, source: source === 'midi' ? 'midi' : 'board' });
  }, [result, source, push]);

  return { trail, push, clear: () => setTrail([]) };
}
