import { useState } from 'react';
import type { Frets } from '../../core/music/fretboard';
import { voicingOptions } from '../../core/songbook/voicingPlan';
import { ChordDiagram } from '../../ui/ChordDiagram';

interface Props {
  chords: string[];
  shapes: Record<string, Frets>;
  strings: number[];
  capo: number;
  onChoose: (symbol: string, frets: Frets) => void;
  onShow: (symbol: string, frets: Frets | null) => void;
}

/** Аккорды песни с выбранными аппликатурами; клик — выбрать другую аппликатуру. */
export function ShapePicker({ chords, shapes, strings, capo, onChoose, onShow }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="shape-strip">
      {chords.map((c) => {
        const options = voicingOptions(c, strings, capo);
        const frets = shapes[c] ?? voicingOptions(c, strings, capo, 1)[0]?.frets ?? null;
        return (
          <div key={c} className={`shape-cell ${open === c ? 'open' : ''}`}>
            <button className="shape-main" onClick={() => onShow(c, frets)} title="Показать на грифе">
              <b>{c}</b>
              {frets ? <ChordDiagram frets={frets} capo={capo} size={64} /> : <small>нет аппликатуры</small>}
            </button>
            {options.length > 1 && (
              <button className="link small" onClick={() => setOpen(open === c ? null : c)}>
                {open === c ? 'закрыть' : `варианты (${options.length})`}
              </button>
            )}
            {open === c && (
              <div className="shape-options">
                {options.map((o, i) => (
                  <button
                    key={i}
                    className={`shape-option ${frets && o.frets.join() === frets.join() ? 'on' : ''}`}
                    onClick={() => {
                      onChoose(c, o.frets);
                      setOpen(null);
                    }}
                  >
                    <ChordDiagram frets={o.frets} capo={capo} size={58} />
                    <small>{o.position ? `${o.position} лад` : 'открытый'}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
