import { useMemo, useState } from 'react';
import type { Board } from '../music/fretboard';
import { mod12, midiName, pcName, pcNameRu } from '../music/notes';
import { FRET_COUNT, STRING_COUNT } from '../music/tunings';

export type Orientation = 'horizontal' | 'vertical';
export type DotLabel = 'note' | 'degree';

interface Props {
  board: Board;
  tuning: number[];
  orientation: Orientation;
  showNotes: boolean;
  realistic: boolean;
  dotLabel: DotLabel;
  /** Ноты, пришедшие с MIDI-клавиатуры (подсвечиваются на всех позициях грифа). */
  midiNotes: Set<number>;
  /** Высотный класс → ступень определённого аккорда. */
  degreeByPc?: Map<number, string>;
  rootPc?: number;
  onToggleFret: (string: number, fret: number) => void;
  onCycleNut: (string: number) => void;
  onMuteString: (string: number) => void;
}

// Геометрия в «продольных» (вдоль струн) и «поперечных» координатах.
const LABEL_ZONE = 34;
const NUT_ZONE = 50;
const NUT_POS = LABEL_ZONE + NUT_ZONE;
const FRET_LEN = 1060;
const GAP = 40;
const MARGIN = 46;
const ACROSS_TOTAL = MARGIN * 2 + GAP * (STRING_COUNT - 1);
const ALONG_TOTAL = NUT_POS + FRET_LEN + 16;
const INLAYS = [3, 5, 7, 9, 15];
const DOT_R = 14;

/** Координата лада: лады постепенно сужаются, как на настоящем грифе (но мягче). */
const FRET_X: number[] = (() => {
  const widths = Array.from({ length: FRET_COUNT }, (_, i) => Math.pow(0.955, i));
  const total = widths.reduce((a, b) => a + b, 0);
  const xs = [NUT_POS];
  let acc = 0;
  for (const w of widths) {
    acc += w;
    xs.push(NUT_POS + (FRET_LEN * acc) / total);
  }
  return xs;
})();

const DEGREE_LABEL: Record<string, string> = { '1': 'R' };

export function Fretboard(props: Props) {
  const { board, tuning, orientation, showNotes, realistic, dotLabel, midiNotes, degreeByPc, rootPc } = props;
  const [hover, setHover] = useState<{ s: number; f: number } | null>(null);
  const horizontal = orientation === 'horizontal';

  // Горизонтально: 1-я струна (e) сверху, как смотрит гитарист. Вертикально: 6-я струна слева.
  const across = (s: number) => MARGIN + (horizontal ? STRING_COUNT - 1 - s : s) * GAP;
  const xy = (along: number, acr: number): [number, number] => (horizontal ? [along, acr] : [acr, along]);
  const rect = (a0: number, a1: number, c0: number, c1: number) => {
    const [x0, y0] = xy(a0, c0);
    const [x1, y1] = xy(a1, c1);
    return { x: Math.min(x0, x1), y: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) };
  };
  const cellCenter = (s: number, f: number): [number, number] =>
    f === 0 ? xy(LABEL_ZONE + NUT_ZONE / 2, across(s)) : xy((FRET_X[f - 1] + FRET_X[f]) / 2, across(s));

  const boardTop = MARGIN - GAP / 2;
  const boardBottom = MARGIN + GAP * (STRING_COUNT - 1) + GAP / 2;
  const viewW = horizontal ? ALONG_TOTAL : ACROSS_TOTAL;
  const viewH = horizontal ? ACROSS_TOTAL : ALONG_TOTAL;

  const sounding = useMemo(() => {
    // Какие точки реально звучат (в реалистичном режиме — только верхняя на струне).
    return board.map((s) => {
      if (s.muted) return new Set<number>();
      const pos = [...(s.open ? [0] : []), ...s.frets];
      return new Set(realistic && pos.length ? [Math.max(...pos)] : pos);
    });
  }, [board, realistic]);

  const label = (midi: number) => {
    if (dotLabel === 'degree' && degreeByPc?.has(mod12(midi))) {
      const d = degreeByPc.get(mod12(midi))!;
      return DEGREE_LABEL[d] ?? d;
    }
    return pcName(midi);
  };

  const hoverInfo = hover
    ? (() => {
        const midi = tuning[hover.s] + hover.f;
        const where = hover.f === 0 ? 'открытая струна' : `${hover.f} лад`;
        return {
          title: `${midiName(midi)} · ${pcNameRu(midi)}`,
          sub: `${STRING_COUNT - hover.s}-я струна, ${where}`,
        };
      })()
    : null;

  return (
    <svg
      className={`fretboard ${orientation}`}
      viewBox={`0 0 ${viewW} ${viewH}`}
      preserveAspectRatio="xMidYMid meet"
      onMouseLeave={() => setHover(null)}
      role="img"
      aria-label="Гриф гитары"
    >
      <defs>
        <linearGradient id="wood" x1="0" y1="0" x2={horizontal ? '0' : '1'} y2={horizontal ? '1' : '0'}>
          <stop offset="0" style={{ stopColor: 'var(--wood-1)' }} />
          <stop offset="0.5" style={{ stopColor: 'var(--wood-2)' }} />
          <stop offset="1" style={{ stopColor: 'var(--wood-1)' }} />
        </linearGradient>
      </defs>

      {/* Накладка грифа */}
      <rect {...rect(NUT_POS, FRET_X[FRET_COUNT] + 6, boardTop, boardBottom)} fill="url(#wood)" rx={4} />

      {/* Инкрустации */}
      {INLAYS.map((f) => {
        const [cx, cy] = xy((FRET_X[f - 1] + FRET_X[f]) / 2, MARGIN + GAP * 2.5);
        return <circle key={f} cx={cx} cy={cy} r={7} className="inlay" />;
      })}
      {[1.5, 3.5].map((k) => {
        const [cx, cy] = xy((FRET_X[11] + FRET_X[12]) / 2, MARGIN + GAP * k);
        return <circle key={k} cx={cx} cy={cy} r={7} className="inlay" />;
      })}

      {/* Лады и порожек */}
      {FRET_X.map((a, i) => {
        const [x1, y1] = xy(a, boardTop);
        const [x2, y2] = xy(a, boardBottom);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className={i === 0 ? 'nut' : 'fret-wire'} />;
      })}

      {/* Номера ладов */}
      {FRET_X.slice(1).map((_, i) => {
        const f = i + 1;
        const [x, y] = xy((FRET_X[f - 1] + FRET_X[f]) / 2, boardBottom + 16);
        return (
          <text key={f} x={x} y={y} className={`fret-num ${INLAYS.includes(f) || f === 12 ? 'marked' : ''}`}>
            {f}
          </text>
        );
      })}

      {/* Струны и их названия */}
      {tuning.map((open, s) => {
        const [x1, y1] = xy(NUT_POS, across(s));
        const [x2, y2] = xy(FRET_X[FRET_COUNT] + 6, across(s));
        const [lx, ly] = xy(LABEL_ZONE / 2, across(s));
        return (
          <g key={s}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              className={`string ${board[s].muted ? 'muted' : ''}`}
              strokeWidth={3.4 - s * 0.42}
            />
            <text x={lx} y={ly} className="string-label">
              {pcName(open)}
            </text>
          </g>
        );
      })}

      {/* Подсветка клетки под курсором */}
      {hover && (
        <rect
          {...(hover.f === 0
            ? rect(LABEL_ZONE + 3, NUT_POS - 3, across(hover.s) - GAP / 2, across(hover.s) + GAP / 2)
            : rect(FRET_X[hover.f - 1], FRET_X[hover.f], across(hover.s) - GAP / 2, across(hover.s) + GAP / 2))}
          className="hover-cell"
          rx={6}
        />
      )}

      {/* Названия нот на всех позициях */}
      {showNotes &&
        tuning.map((open, s) =>
          Array.from({ length: FRET_COUNT }, (_, i) => i + 1)
            .filter((f) => !board[s].frets.includes(f))
            .map((f) => {
              const [x, y] = cellCenter(s, f);
              return (
                <text key={`${s}-${f}`} x={x} y={y} className="note-name">
                  {pcName(open + f)}
                </text>
              );
            }),
        )}

      {/* Метки у порожка: O — открытая, X — заглушена */}
      {board.map((st, s) => {
        const [cx, cy] = cellCenter(s, 0);
        const midi = tuning[s];
        if (st.muted)
          return (
            <text key={s} x={cx} y={cy} className="mute-mark">
              ✕
            </text>
          );
        if (st.open)
          return (
            <g key={s}>
              <circle
                cx={cx}
                cy={cy}
                r={11}
                className={`open-mark ${rootPc === mod12(midi) ? 'root' : ''} ${sounding[s].has(0) ? '' : 'silent'}`}
              />
              {dotLabel === 'degree' && degreeByPc?.has(mod12(midi)) && (
                <text x={cx} y={cy} className="open-label">
                  {label(midi)}
                </text>
              )}
            </g>
          );
        return null;
      })}

      {/* Подсветка нот с MIDI-клавиатуры */}
      {[...midiNotes].flatMap((m) =>
        tuning.flatMap((open, s) => {
          const f = m - open;
          if (f < 0 || f > FRET_COUNT) return [];
          const [cx, cy] = cellCenter(s, f);
          return [<circle key={`m${m}-${s}`} cx={cx} cy={cy} r={DOT_R + 4} className="midi-ghost" />];
        }),
      )}

      {/* Точки нажатия */}
      {board.map((st, s) =>
        st.frets.map((f) => {
          const [cx, cy] = cellCenter(s, f);
          const midi = tuning[s] + f;
          const isRoot = rootPc === mod12(midi);
          return (
            <g key={`${s}-${f}`} className={`dot ${isRoot ? 'root' : ''} ${sounding[s].has(f) ? '' : 'silent'}`}>
              <circle cx={cx} cy={cy} r={DOT_R} />
              <text x={cx} y={cy}>
                {label(midi)}
              </text>
            </g>
          );
        }),
      )}

      {/* Прозрачные зоны для кликов */}
      {tuning.map((_, s) => (
        <g key={`hit${s}`}>
          <rect
            {...rect(LABEL_ZONE, NUT_POS, across(s) - GAP / 2, across(s) + GAP / 2)}
            className="hit"
            onMouseEnter={() => setHover({ s, f: 0 })}
            onClick={() => props.onCycleNut(s)}
            onContextMenu={(e) => {
              e.preventDefault();
              props.onMuteString(s);
            }}
          >
            <title>Клик: пусто → O (открытая) → X (заглушена). Правый клик: заглушить.</title>
          </rect>
          {Array.from({ length: FRET_COUNT }, (_, i) => i + 1).map((f) => (
            <rect
              key={f}
              {...rect(FRET_X[f - 1], FRET_X[f], across(s) - GAP / 2, across(s) + GAP / 2)}
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
      {hover && hoverInfo && (() => {
        const [cx, cy] = cellCenter(hover.s, hover.f);
        const w = 150;
        const h = 40;
        let tx = cx - w / 2;
        let ty = horizontal ? cy - GAP / 2 - h - 4 : cy - GAP - h / 2;
        if (!horizontal) tx = cx + 22 + w > viewW ? cx - w - 22 : cx + 22;
        if (horizontal && ty < 0) ty = cy + GAP / 2 + 4;
        tx = Math.max(2, Math.min(viewW - w - 2, tx));
        ty = Math.max(2, Math.min(viewH - h - 2, ty));
        return (
          <g className="tooltip" pointerEvents="none">
            <rect x={tx} y={ty} width={w} height={h} rx={7} />
            <text x={tx + w / 2} y={ty + 15} className="tt-title">
              {hoverInfo.title}
            </text>
            <text x={tx + w / 2} y={ty + 30} className="tt-sub">
              {hoverInfo.sub}
            </text>
          </g>
        );
      })()}
    </svg>
  );
}
