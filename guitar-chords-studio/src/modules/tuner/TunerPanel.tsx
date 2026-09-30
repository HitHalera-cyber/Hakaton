import './tuner.css';
import { audio } from '../../core/audio/engine';
import { freqToMidi } from '../../core/analysis/pitch';
import { usePitch } from '../../services/usePitch';
import { midiName, pcName, pcNameRu } from '../../core/music/notes';

interface Props {
  tuning: number[];
  capo: number;
}

export function TunerPanel({ tuning, capo }: Props) {
  const { active, error, reading, level, start, stop } = usePitch();

  // Ближайшая струна текущего строя.
  const target = reading
    ? tuning
        .map((open, s) => ({ s, midi: open + capo, diff: freqToMidi(reading.freq) - (open + capo) }))
        .sort((a, b) => Math.abs(a.diff) - Math.abs(b.diff))[0]
    : null;
  const targetCents = target ? Math.round(target.diff * 100) : 0;
  const inTune = reading && Math.abs(reading.cents) <= 5;
  const angle = reading ? Math.max(-50, Math.min(50, reading.cents)) * 1.6 : 0;

  return (
    <div className="tab-body">
      <div className="row">
        {active ? (
          <button className="btn" onClick={stop}>
            ■ Выключить микрофон
          </button>
        ) : (
          <button className="btn primary" onClick={start}>
            🎤 Включить тюнер
          </button>
        )}
        {active && (
          <div className="level" title="Уровень сигнала">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className={`tuner ${active ? '' : 'off'}`}>
        <svg viewBox="0 0 240 130" className="tuner-gauge">
          <path d="M 20 120 A 100 100 0 0 1 220 120" className="arc" />
          {[-50, -25, 0, 25, 50].map((c) => {
            const a = ((c * 1.6 - 90) * Math.PI) / 180;
            return (
              <g key={c}>
                <line
                  x1={120 + 88 * Math.cos(a)}
                  y1={120 + 88 * Math.sin(a)}
                  x2={120 + 100 * Math.cos(a)}
                  y2={120 + 100 * Math.sin(a)}
                  className="tick"
                />
                <text x={120 + 76 * Math.cos(a)} y={120 + 76 * Math.sin(a)} className="tick-label">
                  {c > 0 ? `+${c}` : c}
                </text>
              </g>
            );
          })}
          <line x1="120" y1="120" x2="120" y2="30" className={`needle ${inTune ? 'ok' : ''}`} transform={`rotate(${angle} 120 120)`} />
          <circle cx="120" cy="120" r="6" className="hub" />
        </svg>
        <div className={`tuner-note ${inTune ? 'ok' : ''}`}>
          {reading ? (
            <>
              <b>{pcName(reading.midi)}</b>
              <sub>{Math.floor(reading.midi / 12) - 1}</sub>
            </>
          ) : (
            '—'
          )}
        </div>
        <div className="tuner-info">
          {reading ? (
            <>
              {pcNameRu(reading.midi)} · {reading.freq.toFixed(1)} Гц · {reading.cents > 0 ? '+' : ''}
              {reading.cents} центов
            </>
          ) : active ? (
            'Сыграйте одну открытую струну'
          ) : (
            'Включите тюнер и разрешите доступ к микрофону'
          )}
        </div>
        {target && reading && (
          <div className={`tuner-hint ${Math.abs(targetCents) <= 5 ? 'ok' : ''}`}>
            {tuning.length - target.s}-я струна ({midiName(target.midi)}):{' '}
            {Math.abs(targetCents) <= 5
              ? 'настроена ✓'
              : targetCents < 0
                ? `ниже на ${-targetCents} ц — подтяните`
                : `выше на ${targetCents} ц — ослабьте`}
          </div>
        )}
      </div>

      <div className="row">
        <span className="hint">Эталон:</span>
        {tuning.map((open, s) => (
          <button key={s} className="btn small" onClick={() => audio.playNote(open + capo, 0.9)} title={`Сыграть ${midiName(open + capo)}`}>
            {pcName(open + capo)}
          </button>
        ))}
      </div>

      <p className="hint">Чтобы узнать, какой аккорд вы играете, откройте «👂 Слушать гитару».</p>
    </div>
  );
}
