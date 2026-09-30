import { useMemo, useState } from 'react';
import type { Frets } from '../../core/music/fretboard';
import { pcName } from '../../core/music/notes';
import { PROGRESSIONS, keyChords, keyRootSpelling, progressionChords, type KeyChord, type KeyMode } from '../../core/music/scales';
import { spelledName } from '../../core/music/notes';
import { generateVoicings } from '../../core/music/voicings';
import { ChordDiagram } from '../../ui/ChordDiagram';

export interface ProgressionChord {
  symbol: string;
  nameRu: string;
  frets: Frets;
}

interface Props {
  tuning: number[];
  capo: number;
  onPick: (frets: Frets, symbol: string) => void;
  onPlayProgression: (chords: ProgressionChord[]) => void;
  onToSequence: (chords: ProgressionChord[]) => void;
}

const FUNC_NAMES: Record<string, string> = { T: 'тоника', S: 'субдоминанта', D: 'доминанта' };

export function KeyPanel({ tuning, capo, onPick, onPlayProgression, onToSequence }: Props) {
  const [tonic, setTonic] = useState(0);
  const [mode, setMode] = useState<KeyMode>('major');
  const [sevenths, setSevenths] = useState(false);
  const [progId, setProgId] = useState(PROGRESSIONS[0].id);

  const bestFrets = (c: KeyChord): Frets | null => generateVoicings(c.rootPc, c.template, tuning, { capo, limit: 1 })[0]?.frets ?? null;

  const chords = useMemo(() => keyChords(tonic, mode, sevenths), [tonic, mode, sevenths]);
  const shapes = useMemo(() => chords.map(bestFrets), [chords, tuning, capo]);
  const progressions = PROGRESSIONS.filter((p) => !p.mode || p.mode === mode);
  const prog = progressions.find((p) => p.id === progId) ?? progressions[0];

  const progChords = (): ProgressionChord[] =>
    progressionChords(tonic, mode, prog)
      .map((c) => ({ symbol: c.symbol, nameRu: c.nameRu, frets: bestFrets(c) }))
      .filter((c): c is ProgressionChord => c.frets != null);

  const keyName = spelledName(keyRootSpelling(tonic, mode)) + (mode === 'major' ? ' мажор' : ' минор');

  return (
    <div className="tab-body">
      <div className="root-picker">
        {Array.from({ length: 12 }, (_, pc) => (
          <button key={pc} className={pc === tonic ? 'on' : ''} onClick={() => setTonic(pc)}>
            {pcName(pc)}
          </button>
        ))}
      </div>
      <div className="row">
        <div className="segmented">
          <button className={mode === 'major' ? 'on' : ''} onClick={() => setMode('major')}>
            Мажор
          </button>
          <button className={mode === 'minor' ? 'on' : ''} onClick={() => setMode('minor')}>
            Минор
          </button>
        </div>
        <label className="check">
          <input type="checkbox" checked={sevenths} onChange={(e) => setSevenths(e.target.checked)} />
          Септаккорды
        </label>
        <span className="hint">Тональность: {keyName}</span>
      </div>

      <div className="key-chords">
        {chords.map((c, i) => (
          <button
            key={i}
            className={`key-chord f-${c.func}`}
            disabled={!shapes[i]}
            onClick={() => shapes[i] && onPick(shapes[i]!, c.symbol)}
            title={`${c.nameRu} — ${FUNC_NAMES[c.func]}`}
          >
            <span className="roman">{c.roman}</span>
            <span className="sym">{c.symbol}</span>
            {shapes[i] && <ChordDiagram frets={shapes[i]!} capo={capo} size={64} fingers={false} />}
          </button>
        ))}
      </div>

      <label className="field">
        <span>Популярная последовательность</span>
        <select value={prog.id} onChange={(e) => setProgId(e.target.value)}>
          {progressions.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <div className="prog-preview">
        {progressionChords(tonic, mode, prog).map((c, i) => (
          <span key={i}>{c.symbol}</span>
        ))}
      </div>
      <div className="row">
        <button className="btn primary" onClick={() => onPlayProgression(progChords())}>
          ▶ Проиграть
        </button>
        <button
          className="btn"
          onClick={() => onToSequence(progChords())}
          title="Заменить последовательность на вкладке «Последовательность»"
        >
          → В последовательность
        </button>
      </div>
      <p className="hint">
        Цвет аккорда — его функция: тоника (устойчивость), субдоминанта (движение), доминанта (напряжение, тянет к тонике).
      </p>
    </div>
  );
}
