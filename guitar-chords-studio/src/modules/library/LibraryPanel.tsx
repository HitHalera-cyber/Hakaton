import './library.css';
import { useEffect, useMemo, useState } from 'react';
import { CHORD_TEMPLATES } from '../../core/music/chords';
import { chordPitchClasses, parseChordSymbol } from '../../core/music/chordParse';
import type { Frets } from '../../core/music/fretboard';
import { pcName, spelledName, spellInterval } from '../../core/music/notes';
import { keyRootSpelling } from '../../core/music/scales';
import { fretsToString, generateVoicings } from '../../core/music/voicings';
import { parseDegree } from '../../core/music/chords';
import { ChordDiagram } from '../../ui/ChordDiagram';

export interface ChordRef {
  rootPc: number;
  templateId: string;
  bassPc?: number;
}

interface Props {
  tuning: number[];
  capo: number;
  current?: ChordRef;
  request?: { ref: ChordRef; nonce: number } | null;
  onPick: (frets: Frets, symbol: string) => void;
}

const ROOTS = Array.from({ length: 12 }, (_, pc) => pc);

export function LibraryPanel({ tuning, capo, current, request, onPick }: Props) {
  const [ref, setRef] = useState<ChordRef>({ rootPc: 0, templateId: 'maj' });
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [picked, setPicked] = useState<number | null>(null);

  // Внешний запрос (например, из поиска в шапке или «аппликатуры текущего аккорда»).
  useEffect(() => {
    if (request) setRef(request.ref);
  }, [request]);

  const template = CHORD_TEMPLATES.find((t) => t.id === ref.templateId) ?? CHORD_TEMPLATES[0];
  const minorLike = template.degrees.includes('b3') && !template.degrees.includes('3');
  const root = keyRootSpelling(ref.rootPc, minorLike ? 'minor' : 'major');
  const symbol = spelledName(root) + template.suffix + (ref.bassPc != null ? '/' + pcName(ref.bassPc) : '');
  const notes = template.degrees.map((d) => {
    const p = parseDegree(d);
    return spelledName(spellInterval(root, p.letterSteps, p.semis));
  });
  const optional = new Set(
    chordPitchClasses(ref.rootPc, template)
      .filter((t) => t.optional)
      .map((t) => t.degree),
  );

  const voicings = useMemo(
    () => generateVoicings(ref.rootPc, template, tuning, { capo, bassPc: ref.bassPc, limit: 12 }),
    [ref, template, tuning, capo],
  );

  useEffect(() => setPicked(null), [ref, tuning, capo]);

  const search = () => {
    const parsed = parseChordSymbol(query);
    if (!parsed) {
      setError('Не понял обозначение. Примеры: Am, C7, Fmaj7, F#m7b5, Dm/F, Gsus4, Bb, Cadd9');
      return;
    }
    setError('');
    setRef({ rootPc: parsed.rootPc, templateId: parsed.template.id, bassPc: parsed.bassPc });
  };

  return (
    <div className="tab-body">
      <div className="row">
        <input
          className="text-input grow"
          placeholder="Найти аккорд: Am, Cmaj7, Dm/F, F#m7b5…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') search();
            e.stopPropagation();
          }}
        />
        <button className="btn primary" onClick={search}>
          Найти
        </button>
        {current && (
          <button className="btn" onClick={() => setRef(current)} title="Показать другие аппликатуры аккорда, который сейчас на грифе">
            Аккорд с грифа
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className="root-picker">
        {ROOTS.map((pc) => (
          <button key={pc} className={pc === ref.rootPc ? 'on' : ''} onClick={() => setRef({ ...ref, rootPc: pc, bassPc: undefined })}>
            {pcName(pc)}
          </button>
        ))}
      </div>
      <label className="field">
        <span>Тип аккорда</span>
        <select value={ref.templateId} onChange={(e) => setRef({ ...ref, templateId: e.target.value, bassPc: undefined })}>
          {CHORD_TEMPLATES.map((t) => (
            <option key={t.id} value={t.id}>
              {(t.suffix || 'мажор') + ' — ' + t.ru}
            </option>
          ))}
        </select>
      </label>

      <div className="lib-head">
        <span className="lib-symbol">{symbol}</span>
        <span className="lib-notes">
          {notes.map((n, i) => (
            <span
              key={i}
              className={optional.has(template.degrees[i]) ? 'opt' : ''}
              title={optional.has(template.degrees[i]) ? 'Эту ноту можно не играть' : undefined}
            >
              {n}
            </span>
          ))}
        </span>
      </div>

      {voicings.length === 0 ? (
        <p className="hint">На этом инструменте удобных аппликатур не нашлось.</p>
      ) : (
        <div className="voicing-grid">
          {voicings.map((v, i) => (
            <button
              key={fretsToString(v.frets) + i}
              className={`voicing ${picked === i ? 'on' : ''}`}
              onClick={() => {
                setPicked(i);
                onPick(v.frets, symbol);
              }}
              title="Поставить на гриф и сыграть"
            >
              <ChordDiagram frets={v.frets} capo={capo} />
              <span className="v-pos">{v.position <= capo ? 'открытая' : `${v.position} лад`}</span>
              <span className="v-tab">{fretsToString(v.frets)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
