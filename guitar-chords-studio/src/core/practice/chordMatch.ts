// Совпадает ли услышанный аккорд с заданным. Распознавание иногда путает Am и Am7, C и Cmaj7 —
// поэтому для упражнений достаточно совпадения тоники и «лада» (мажорный/минорный).

import { parseChordSymbol } from '../music/chordParse';
import { CHORD_TEMPLATES } from '../music/chords';

const minorLike = (templateId: string) => {
  const t = CHORD_TEMPLATES.find((x) => x.id === templateId);
  return Boolean(t && t.degrees.includes('b3') && !t.degrees.includes('3'));
};

export function matchesChord(target: string, heard: { rootPc: number; templateId: string }): boolean {
  const p = parseChordSymbol(target);
  if (!p) return false;
  return p.rootPc === heard.rootPc && minorLike(p.template.id) === minorLike(heard.templateId);
}
