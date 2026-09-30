import type { SongLine } from '../../core/songbook/chordpro';

interface Props {
  lines: SongLine[];
  /** Аккорд, который сейчас подсвечен (последний нажатый). */
  active?: string;
  onChord: (symbol: string) => void;
}

/** Текст песни с аккордами над слогами. */
export function SongSheet({ lines, active, onChord }: Props) {
  return (
    <div className="song-sheet">
      {lines.map((l, i) =>
        l.kind === 'section' ? (
          <h4 key={i} className="sb-section">
            {l.title}
          </h4>
        ) : l.kind === 'empty' ? (
          <div key={i} className="sb-gap" />
        ) : (
          <div key={i} className="sb-line">
            {l.parts.map((p, j) => (
              <span key={j} className={`sb-part ${p.chord ? 'has-chord' : ''}`}>
                {p.chord && (
                  <button
                    className={`sb-chord ${p.chord === active ? 'on' : ''}`}
                    onClick={() => onChord(p.chord!)}
                    title="Показать на грифе"
                  >
                    {p.chord}
                  </button>
                )}
                <span className="sb-text">{p.text || (p.chord ? ' ' : '')}</span>
              </span>
            ))}
          </div>
        ),
      )}
    </div>
  );
}
