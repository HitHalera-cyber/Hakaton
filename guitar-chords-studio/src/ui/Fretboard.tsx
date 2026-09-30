import './fretboard.css';
import { useMemo, useState } from 'react';
import { fingerKey, type Fingering } from '../core/music/fingering';
import type { Board } from '../core/music/fretboard';
import { mod12, midiName, pcName, pcNameRu } from '../core/music/notes';
import { FRET_COUNT } from '../core/music/tunings';

export type DotLabel = 'note' | 'degree' | 'finger';

export interface ScaleOverlay {
  rootPc: number;
  /** Высотный класс → ступень гаммы. */
  degrees: Map<number, string>;
}

export interface CellFlash {
  s: number;
  f: number;
  ok: boolean;
}

interface Props {
  board: Board;
  tuning: number[];
  capo: number;
  showNotes: boolean;
  dotLabel: DotLabel;
  /** Ноты с MIDI-клавиатуры (подсвечиваются на всех позициях грифа). */
  midiNotes: Set<number>;
  /** Высотный класс → ступень определённого аккорда. */
  degreeByPc?: Map<number, string>;
  rootPc?: number;
  fingering?: Fingering;
  scale?: ScaleOverlay | null;
  flash?: CellFlash | null;
  onToggleFret: (string: number, fret: number) => void;
  onCycleNut: (string: number) => void;
  onMuteString: (string: number) => void;
}

// Геометрия: x — вдоль струн (лады), y — поперёк (струны).
const LABEL_ZONE = 34;
const NUT_ZONE = 50;
const NUT_X = LABEL_ZONE + NUT_ZONE;
const FRET_LEN = 1060;
const GAP = 40;
const MARGIN = 40;
const INLAYS = [3, 5, 7, 9, 15];
const DOT_R = 14;
const VIEW_W = NUT_X + FRET_LEN + 16;

/** Координата лада: лады постепенно сужаются, как на настоящем грифе (но мягче). */
const FRET_X: number[] = (() => {
  const widths = Array.from({ length: FRET_COUNT }, (_, i) => Math.pow(0.955, i));
  const total = widths.reduce((a, b) => a + b, 0);
  const xs = [NUT_X];
  let acc = 0;
  for (const w of widths) {
    acc += w;
    xs.push(NUT_X + (FRET_LEN * acc) / total);
  }
  return xs;
})();

const DEGREE_LABEL: Record<string, string> = { '1': 'R' };
const cellX = (f: number) => (f === 0 ? LABEL_ZONE + NUT_ZONE / 2 : (FRET_X[f - 1] + FRET_X[f]) / 2);

export function Fretboard(props: Props) {
  const { board, tuning, capo, showNotes, dotLabel, midiNotes, degreeByPc, rootPc, fingering, scale, flash } = props;
  const [hover, setHover] = useState<{ s: number; f: number } | null>(null);
  const n = tuning.length;

  // Верхняя (самая тонкая) струна сверху, как смотрит гитарист.
  const y = (s: number) => MARGIN + (n - 1 - s) * GAP;
  const top = MARGIN - GAP / 2;
  const bottom = MARGIN + GAP * (n - 1) + GAP / 2;
  const viewH = bottom + 26;
  const frets = useMemo(() => Array.from({ length: FRET_COUNT }, (_, i) => i + 1), []);

  const label = (midi: number, s: number, f: number) => {
    if (dotLabel === 'finger') return String(fingering?.fingers.get(fingerKey(s, f)) ?? '');
    if (dotLabel === 'degree' && degreeByPc?.has(mod12(midi))) {
      const d = degreeByPc.get(mod12(midi))!;
      return DEGREE_LABEL[d] ?? d;
    }
    return pcName(midi);
  };

  const hoverInfo = hover
    ? (() => {
        const fret = hover.f === 0 ? capo : hover.f;
        const midi = tuning[hover.s] + fret;
        const where = hover.f === 0 ? (capo ? `открытая (каподастр ${capo})` : 'открытая струна') : `${hover.f} лад`;
        return { title: `${midiName(midi)} · ${pcNameRu(midi)}`, sub: `${n - hover.s}-я струна, ${where}` };
      })()
    : null;

  const barre = dotLabel === 'finger' ? fingering?.barre : null;

  return (
    <svg
      className="fretboard"
      viewBox={`0 0 ${VIEW_W} ${viewH}`}
      preserveAspectRatio="xMidYMid meet"
      onMouseLeave={() => setHover(null)}
      role="img"
      aria-label="Гриф"
    >
      <defs>
        <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: 'var(--wood-1)' }} />
          <stop offset="0.5" style={{ stopColor: 'var(--wood-2)' }} />
          <stop offset="1" style={{ stopColor: 'var(--wood-1)' }} />
        </linearGradient>
      </defs>

      {/* Накладка грифа */}
      <rect x={NUT_X} y={top} width={FRET_X[FRET_COUNT] + 6 - NUT_X} height={bottom - top} fill="url(#wood)" rx={4} />

      {/* Лады под каподастром недоступны */}
      {capo > 0 && <rect x={NUT_X} y={top} width={FRET_X[capo] - NUT_X} height={bottom - top} className="capo-shade" />}

      {/* Инкрустации */}
      {INLAYS.map((f) => (
        <circle key={f} cx={cellX(f)} cy={(top + bottom) / 2} r={7} className="inlay" />
      ))}
      {[0.3, 0.7].map((k) => (
        <circle key={k} cx={cellX(12)} cy={top + (bottom - top) * k} r={7} className="inlay" />
      ))}

      {/* Лады и порожек */}
      {FRET_X.map((x, i) => (
        <line key={i} x1={x} y1={top} x2={x} y2={bottom} className={i === 0 ? 'nut' : 'fret-wire'} />
      ))}

      {/* Номера ладов */}
      {frets.map((f) => (
        <text key={f} x={cellX(f)} y={bottom + 15} className={`fret-num ${INLAYS.includes(f) || f === 12 ? 'marked' : ''}`}>
          {f}
        </text>
      ))}

      {/* Струны и их названия */}
      {tuning.map((open, s) => (
        <g key={s}>
          <line
            x1={NUT_X}
            y1={y(s)}
            x2={FRET_X[FRET_COUNT] + 6}
            y2={y(s)}
            className={`string ${board[s]?.muted ? 'muted' : ''}`}
            strokeWidth={Math.max(1.1, 3.6 - ((open - 23) / 50) * 2.6)}
          />
          <text x={LABEL_ZONE / 2} y={y(s)} className="string-label">
            {pcName(open)}
          </text>
        </g>
      ))}

      {/* Каподастр */}
      {capo > 0 && (
        <g className="capo">
          <rect x={FRET_X[capo] - 13} y={top - 6} width={11} height={bottom - top + 12} rx={5} />
          <text x={FRET_X[capo] - 7.5} y={top - 14}>
            капо
          </text>
        </g>
      )}

      {/* Подсветка клетки под курсором */}
      {hover && (
        <rect
          x={hover.f === 0 ? LABEL_ZONE + 3 : FRET_X[hover.f - 1]}
          y={y(hover.s) - GAP / 2}
          width={hover.f === 0 ? NUT_ZONE - 6 : FRET_X[hover.f] - FRET_X[hover.f - 1]}
          height={GAP}
          className="hover-cell"
          rx={6}
        />
      )}

      {/* Гамма */}
      {scale &&
        tuning.flatMap((open, s) =>
          frets
            .filter((f) => f > capo && scale.degrees.has(mod12(open + f)) && !board[s]?.frets.includes(f))
            .map((f) => {
              const pc = mod12(open + f);
              const isRoot = pc === scale.rootPc;
              return (
                <g key={`sc${s}-${f}`} className={`scale-mark ${isRoot ? 'root' : ''}`}>
                  <circle cx={cellX(f)} cy={y(s)} r={12} />
                  <text x={cellX(f)} y={y(s)}>
                    {dotLabel === 'degree' ? scale.degrees.get(pc) : pcName(pc)}
                  </text>
                </g>
              );
            }),
        )}

      {/* Названия нот на всех позициях */}
      {showNotes &&
        tuning.flatMap((open, s) =>
          frets
            .filter((f) => f > capo && !board[s]?.frets.includes(f) && !(scale && scale.degrees.has(mod12(open + f))))
            .map((f) => (
              <g key={`n${s}-${f}`} className="note-pill">
                <circle cx={cellX(f)} cy={y(s)} r={11} />
                <text x={cellX(f)} y={y(s)}>
                  {pcName(open + f)}
                </text>
              </g>
            )),
        )}

      {/* Метки у порожка: O — открытая, X — заглушена */}
      {board.map((st, s) => {
        const cx = cellX(0);
        const midi = tuning[s] + capo;
        if (st.muted)
          return (
            <text key={s} x={cx} y={y(s)} className="mute-mark">
              ✕
            </text>
          );
        if (st.open)
          return (
            <g key={s}>
              <circle cx={cx} cy={y(s)} r={11} className={`open-mark ${rootPc === mod12(midi) ? 'root' : ''}`} />
              {dotLabel === 'degree' && degreeByPc?.has(mod12(midi)) && (
                <text x={cx} y={y(s)} className="open-label">
                  {label(midi, s, 0)}
                </text>
              )}
            </g>
          );
        return null;
      })}

      {/* Ноты с MIDI-клавиатуры */}
      {[...midiNotes].flatMap((m) =>
        tuning.flatMap((open, s) => {
          const f = m - open;
          if (f < capo || f > FRET_COUNT) return [];
          const cx = f === capo ? cellX(0) : cellX(f);
          return [<circle key={`m${m}-${s}`} cx={cx} cy={y(s)} r={DOT_R + 4} className="midi-ghost" />];
        }),
      )}

      {/* Баррэ */}
      {barre && (
        <rect
          className="barre"
          x={cellX(barre.fret) - DOT_R}
          y={y(barre.toString) - DOT_R}
          width={DOT_R * 2}
          height={y(barre.fromString) - y(barre.toString) + DOT_R * 2}
          rx={DOT_R}
        />
      )}

      {/* Точки нажатия */}
      {board.map((st, s) =>
        st.frets
          .filter((f) => f > capo)
          .map((f) => {
            const midi = tuning[s] + f;
            const isRoot = rootPc === mod12(midi);
            return (
              <g key={`${s}-${f}`} className={`dot ${isRoot ? 'root' : ''}`}>
                <circle cx={cellX(f)} cy={y(s)} r={DOT_R} />
                <text x={cellX(f)} y={y(s)}>
                  {label(midi, s, f)}
                </text>
              </g>
            );
          }),
      )}

      {/* Отметка ответа в тренажёре */}
      {flash && (
        <circle
          key={`${flash.s}-${flash.f}-${flash.ok}`}
          cx={flash.f === capo ? cellX(0) : cellX(flash.f)}
          cy={y(flash.s)}
          r={DOT_R + 3}
          className={`flash ${flash.ok ? 'ok' : 'bad'}`}
        />
      )}

      {/* Прозрачные зоны для кликов */}
      {tuning.map((_, s) => (
        <g key={`hit${s}`}>
          <rect
            x={LABEL_ZONE}
            y={y(s) - GAP / 2}
            width={NUT_ZONE}
            height={GAP}
            className="hit"
            onMouseEnter={() => setHover({ s, f: 0 })}
            onClick={() => props.onCycleNut(s)}
            onContextMenu={(e) => {
              e.preventDefault();
              props.onMuteString(s);
            }}
          >
            <title>Клик: пусто ↔ O (открытая). Правый клик: заглушить струну (X).</title>
          </rect>
          {frets
            .filter((f) => f > capo)
            .map((f) => (
              <rect
                key={f}
                x={FRET_X[f - 1]}
                y={y(s) - GAP / 2}
                width={FRET_X[f] - FRET_X[f - 1]}
                height={GAP}
                className="hit"
                onMouseEnter={() => setHover({ s, f })}
                onClick={() => props.onToggleFret(s, f)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  props.onMuteString(s);
                }}
              />
            ))}
        </g>
      ))}

      {/* Подсказка с названием ноты */}
      {hover &&
        hoverInfo &&
        (() => {
          const cx = cellX(hover.f);
          const w = 350;
          const h = 78;
          let ty = y(hover.s) - GAP / 2 - h - 4;
          if (ty < 0) ty = y(hover.s) + GAP / 2 + 4;
          const tx = Math.max(2, Math.min(VIEW_W - w - 2, cx - w / 2));
          return (
            <g className="tooltip" pointerEvents="none">
              <rect x={tx} y={ty} width={w} height={h} rx={12} />
              <text x={tx + w / 2} y={ty + 30} className="tt-title">
                {hoverInfo.title}
              </text>
              <text x={tx + w / 2} y={ty + 60} className="tt-sub">
                {hoverInfo.sub}
              </text>
            </g>
          );
        })()}
    </svg>
  );
}
