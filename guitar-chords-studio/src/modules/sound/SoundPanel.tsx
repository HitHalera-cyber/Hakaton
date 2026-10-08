import { TIMBRE_NAMES, type PlayMode, type Timbre } from '../../core/audio/engine';
import type { Instrument } from '../../core/music/tunings';

export interface SoundSettings {
  volume: number;
  reverb: number;
  mode: PlayMode;
  arpStepMs: number;
  timbre: Timbre;
  autoPlay: boolean;
}

interface Props {
  settings: SoundSettings;
  instrument: Instrument;
  onChange: (patch: Partial<SoundSettings>) => void;
  onStop: () => void;
}

export function SoundPanel({ settings, instrument, onChange, onStop }: Props) {
  return (
    <div className="tab-body">
      <p className="hint">Бой вниз, бой вверх или перебор — переключатель «Звук» в верхней строке, он действует везде.</p>
      <div className="row">
        <button className="btn" onClick={onStop} title="Esc">
          ■ Стоп
        </button>
      </div>

      <div className="grid2">
        <label className="field">
          <span>Тембр</span>
          <select
            value={settings.timbre}
            onChange={(e) => onChange({ timbre: e.target.value as Timbre })}
            disabled={instrument !== 'guitar'}
            title={instrument !== 'guitar' ? 'Для баса и укулеле тембр выбирается автоматически' : undefined}
          >
            {(Object.keys(TIMBRE_NAMES) as Timbre[]).map((t) => (
              <option key={t} value={t}>
                {TIMBRE_NAMES[t]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="slider">
        <span>Громкость — {Math.round(settings.volume * 100)}%</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.volume}
          onChange={(e) => onChange({ volume: Number(e.target.value) })}
        />
      </label>
      <label className="slider">
        <span>Реверберация (эхо помещения) — {Math.round(settings.reverb * 100)}%</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.reverb}
          onChange={(e) => onChange({ reverb: Number(e.target.value) })}
        />
      </label>
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

      <label className="check">
        <input type="checkbox" checked={settings.autoPlay} onChange={(e) => onChange({ autoPlay: e.target.checked })} />
        Звучит нота, когда ставите точку на гриф (аккорд целиком — кнопкой «Играть»)
      </label>
    </div>
  );
}
