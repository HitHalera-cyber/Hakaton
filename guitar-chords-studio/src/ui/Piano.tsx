import { midiName, mod12 } from '../core/music/notes';

interface Props {
  from: number;
  to: number;
  active: Set<number>;
  range: [number, number];
  onKey: (midi: number) => void;
}

const BLACK = new Set([1, 3, 6, 8, 10]);

/** Мини-клавиатура: показывает ноты с MIDI и позволяет собрать аккорд мышью. */
export function Piano({ from, to, active, range, onKey }: Props) {
  const whites: number[] = [];
  for (let m = from; m <= to; m++) if (!BLACK.has(mod12(m))) whites.push(m);
  const ww = 100 / whites.length;

  return (
    <div className="piano" role="group" aria-label="Клавиатура">
      {whites.map((m, i) => (
        <button
          key={m}
          className={`white ${active.has(m) ? 'on' : ''} ${m < range[0] || m > range[1] ? 'out' : ''}`}
          style={{ left: `${i * ww}%`, width: `${ww}%` }}
          onMouseDown={() => onKey(m)}
          title={midiName(m)}
        >
          {mod12(m) === 0 && <span>{midiName(m)}</span>}
        </button>
      ))}
      {whites.map((m, i) =>
        m + 1 <= to && BLACK.has(mod12(m + 1)) ? (
          <button
            key={m + 1}
            className={`black ${active.has(m + 1) ? 'on' : ''}`}
            style={{ left: `${(i + 1) * ww - ww * 0.3}%`, width: `${ww * 0.6}%` }}
            onMouseDown={() => onKey(m + 1)}
            title={midiName(m + 1)}
          />
        ) : null,
      )}
    </div>
  );
}
