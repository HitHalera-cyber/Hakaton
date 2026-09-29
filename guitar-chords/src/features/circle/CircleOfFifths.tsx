import './circle.css';
import {
  DIM_LABELS,
  KEY_SIGNATURES,
  MAJOR_LABELS,
  MINOR_LABELS,
  inKey,
  romanInKey,
  type CircleKey,
  type CirclePos,
  type Ring,
} from '../../core/music/circle';

interface Props {
  /** Аккорд, который звучит сейчас, — светится. */
  active: CirclePos | null;
  /** Меняется при каждом новом аккорде — перезапускает «вспышку». */
  pulseKey?: string | number;
  /** Предыдущие аккорды (от свежего к старому) — затухающий след. */
  trail: CirclePos[];
  keySel: CircleKey | null;
  center?: { title: string; subtitle?: string };
  onPick?: (pos: CirclePos) => void;
  size?: number;
  compact?: boolean;
}

// Радиусы колец (в единицах viewBox).
const R: Record<Ring, [number, number]> = {
  major: [165, 232],
  minor: [106, 165],
  dim: [70, 106],
};
const LABELS: Record<Ring, string[]> = { major: MAJOR_LABELS, minor: MINOR_LABELS, dim: DIM_LABELS };
const RINGS: Ring[] = ['major', 'minor', 'dim'];

const rad = (deg: number) => (deg * Math.PI) / 180;
const polar = (r: number, deg: number): [number, number] => [r * Math.cos(rad(deg)), r * Math.sin(rad(deg))];
/** Угол центра ячейки: C сверху, дальше по часовой стрелке. */
const angle = (index: number) => -90 + index * 30;

function sector(r0: number, r1: number, index: number): string {
  const a0 = angle(index) - 15 + 0.6;
  const a1 = angle(index) + 15 - 0.6;
  const [x0, y0] = polar(r1, a0);
  const [x1, y1] = polar(r1, a1);
  const [x2, y2] = polar(r0, a1);
  const [x3, y3] = polar(r0, a0);
  return `M${x0},${y0} A${r1},${r1} 0 0 1 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 0 0 ${x3},${y3} Z`;
}

const cellCenter = (p: CirclePos): [number, number] => polar((R[p.ring][0] + R[p.ring][1]) / 2, angle(p.index));
const same = (a: CirclePos | null | undefined, b: CirclePos) => !!a && a.ring === b.ring && a.index === b.index;

export function CircleOfFifths({ active, pulseKey, trail, keySel, center, onPick, size = 480, compact }: Props) {
  const path = [active, ...trail].filter((p): p is CirclePos => p != null).slice(0, 4);

  return (
    <svg
      className={`circle5 ${compact ? 'compact' : ''}`}
      viewBox="-256 -256 512 512"
      width={size}
      height={size}
      role="img"
      aria-label="Квартоквинтовый круг"
    >
      {/* Знаки при ключе */}
      {!compact &&
        KEY_SIGNATURES.map((sig, i) => {
          const [x, y] = polar(246, angle(i));
          return (
            <text key={sig} x={x} y={y} className="cf-sig">
              {sig}
            </text>
          );
        })}

      {RINGS.map((ring) =>
        LABELS[ring].map((label, index) => {
          const pos = { ring, index };
          const trailIdx = trail.findIndex((t) => same(t, pos));
          const classes = [
            'cf-cell',
            `ring-${ring}`,
            keySel && inKey(pos, keySel) ? 'in-key' : '',
            keySel &&
            keySel.index === index &&
            ((keySel.mode === 'major' && ring === 'major') || (keySel.mode === 'minor' && ring === 'minor'))
              ? 'tonic'
              : '',
            same(active, pos) ? 'active' : '',
            !same(active, pos) && trailIdx >= 0 && trailIdx < 3 ? `trail t${trailIdx}` : '',
            onPick ? 'clickable' : '',
          ].join(' ');
          const [tx, ty] = cellCenter(pos);
          const roman = keySel ? romanInKey(pos, keySel) : null;
          return (
            <g key={`${ring}${index}`} className={classes} onClick={() => onPick?.(pos)}>
              <path d={sector(R[ring][0], R[ring][1], index)} />
              <text x={tx} y={ty - (roman && !compact ? 6 : 0)} className="cf-label">
                {label}
              </text>
              {roman && !compact && (
                <text x={tx} y={ty + 13} className="cf-roman">
                  {roman}
                </text>
              )}
            </g>
          );
        }),
      )}

      {/* Путь по кругу: откуда пришли в текущий аккорд */}
      {path.length >= 2 &&
        path.slice(0, -1).map((p, i) => {
          const [x1, y1] = cellCenter(path[i + 1]);
          const [x2, y2] = cellCenter(p);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className={`cf-path p${i}`} />;
        })}

      {/* Вспышка при новом аккорде */}
      {active && <circle key={String(pulseKey)} cx={cellCenter(active)[0]} cy={cellCenter(active)[1]} r={26} className="cf-burst" />}

      <circle r={R.dim[0] - 3} className="cf-center" />
      {center ? (
        <>
          <text y={center.subtitle ? -8 : 0} className="cf-center-title">
            {center.title}
          </text>
          {center.subtitle && (
            <text y={20} className="cf-center-sub">
              {center.subtitle}
            </text>
          )}
        </>
      ) : null}
    </svg>
  );
}
