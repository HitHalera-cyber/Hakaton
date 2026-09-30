import { computeFingering, fingerKey } from '../core/music/fingering';
import { boardFromFrets, type Frets } from '../core/music/fretboard';
import { diagramWindow } from '../core/export/diagram';

interface Props {
  frets: Frets;
  capo?: number;
  fingers?: boolean;
  size?: number;
}

/** Маленькая аккордовая диаграмма: струны вертикально, басовая слева. */
export function ChordDiagram({ frets, capo = 0, fingers = true, size = 92 }: Props) {
  const board = boardFromFrets(frets, capo);
  const n = frets.length;
  const { start, rows } = diagramWindow(board, capo);
  const fing = fingers ? computeFingering(board, capo) : null;
  const gap = 12;
  const rowH = 14;
  const left = 16;
  const top = 16;
  const w = left * 2 + gap * (n - 1);
  const h = top + rowH * rows + 6;
  const x = (s: number) => left + s * gap;
  const yRow = (r: number) => top + r * rowH;

  return (
    <svg className="mini-diagram" viewBox={`0 0 ${w} ${h}`} width={size} height={(size * h) / w}>
      {start === 1 ? (
        <line x1={x(0) - 1} y1={yRow(0)} x2={x(n - 1) + 1} y2={yRow(0)} className="md-nut" />
      ) : (
        <text x={x(0) - 9} y={yRow(0) + rowH / 2} className="md-fret">
          {start}
        </text>
      )}
      {Array.from({ length: rows + 1 }, (_, r) => (
        <line key={`r${r}`} x1={x(0)} y1={yRow(r)} x2={x(n - 1)} y2={yRow(r)} className="md-line" />
      ))}
      {frets.map((_, s) => (
        <line key={`s${s}`} x1={x(s)} y1={yRow(0)} x2={x(s)} y2={yRow(rows)} className="md-line" />
      ))}
      {fing?.barre && fing.barre.fret >= start && (
        <rect
          x={x(fing.barre.fromString) - 5}
          y={yRow(fing.barre.fret - start) + rowH / 2 - 5}
          width={x(fing.barre.toString) - x(fing.barre.fromString) + 10}
          height={10}
          rx={5}
          className="md-dot"
        />
      )}
      {frets.map((f, s) => {
        if (f == null)
          return (
            <text key={s} x={x(s)} y={yRow(0) - 7} className="md-mark">
              ×
            </text>
          );
        if (f <= capo) return <circle key={s} cx={x(s)} cy={yRow(0) - 7} r={3.2} className="md-open" />;
        const cy = yRow(f - start) + rowH / 2;
        const finger = fing?.fingers.get(fingerKey(s, f));
        return (
          <g key={s}>
            <circle cx={x(s)} cy={cy} r={5} className="md-dot" />
            {finger && fingers && (
              <text x={x(s)} y={cy + 0.5} className="md-finger">
                {finger}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
