import { TIMBRE_NAMES, type PlayMode, type Timbre } from '../audio/guitarSynth';

export interface SoundSettings {
  volume: number;
  mode: PlayMode;
  arpStepMs: number;
  timbre: Timbre;
  autoPlay: boolean;
}

interface Props {
  settings: SoundSettings;
  onChange: (patch: Partial<SoundSettings>) => void;
  onPlay: () => void;
  onStop: () => void;
  canPlay: boolean;
}

export function SoundPanel({ settings, onChange, onPlay, onStop, canPlay }: Props) {
  return (
    <section className="panel">
      <h3>Звук</h3>
      <div className="row">
        <button className="btn primary" onClick={onPlay} disabled={!canPlay}>
          ▶ Играть
        </button>
        <button className="btn" onClick={onStop} title="Esc">
          ■ Стоп
        </button>
      </div>

      <div className="segmented" role="radiogroup" aria-label="Способ игры">
        <button className={settings.mode === 'strum' ? 'on' : ''} onClick={() => onChange({ mode: 'strum' })}>
          Одновременно
        </button>
        <button className={settings.mode === 'arpeggio' ? 'on' : ''} onClick={() => onChange({ mode: 'arpeggio' })}>
          Перебор
        </button>
      </div>

      {settings.mode === 'arpeggio' && (
        <label className="slider">
          <span>Скорость перебора</span>
          <input
            type="range"
            min={60}
            max={500}
            step={10}
            value={560 - settings.arpStepMs}
            onChange={(e) => onChange({ arpStepMs: 560 - Number(e.target.value) })}
          />
        </label>
      )}

      <label className="slider">
        <span>Громкость {Math.round(settings.volume * 100)}%</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.volume}
          onChange={(e) => onChange({ volume: Number(e.target.value) })}
        />
      </label>

      <label className="field">
        <span>Тембр</span>
        <select value={settings.timbre} onChange={(e) => onChange({ timbre: e.target.value as Timbre })}>
          {(Object.keys(TIMBRE_NAMES) as Timbre[]).map((t) => (
            <option key={t} value={t}>
              {TIMBRE_NAMES[t]}
            </option>
          ))}
        </select>
      </label>

      <label className="check">
        <input type="checkbox" checked={settings.autoPlay} onChange={(e) => onChange({ autoPlay: e.target.checked })} />
        Играть при изменении точек
      </label>
    </section>
  );
}
