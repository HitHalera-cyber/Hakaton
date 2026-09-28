import { TIMBRE_NAMES, type PlayMode, type Timbre } from '../audio/engine';
import type { Instrument } from '../music/tunings';

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
  onPlay: () => void;
  onStrum: (dir: 'down' | 'up') => void;
  onArpeggio: () => void;
  onStop: () => void;
  canPlay: boolean;
}

export function SoundPanel({ settings, instrument, onChange, onPlay, onStrum, onArpeggio, onStop, canPlay }: Props) {
  return (
    <div className="tab-body">
      <div className="row">
        <button className="btn primary" onClick={onPlay} disabled={!canPlay} title="Пробел">
          ▶ Играть
        </button>
        <button className="btn" onClick={() => onStrum('down')} disabled={!canPlay} title="Удар по струнам сверху вниз (от баса)">
          ↓ Бой вниз
        </button>
        <button className="btn" onClick={() => onStrum('up')} disabled={!canPlay} title="Удар снизу вверх (от тонких струн)">
          ↑ Бой вверх
        </button>
        <button className="btn" onClick={onArpeggio} disabled={!canPlay}>
          ♪ Перебор
        </button>
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
        <label className="field">
          <span>Кнопка «Играть» и автоигра</span>
          <select value={settings.mode} onChange={(e) => onChange({ mode: e.target.value as PlayMode })}>
            <option value="strum">Бой (все струны сразу)</option>
            <option value="arpeggio">Перебор (по одной струне)</option>
          </select>
        </label>
      </div>

      <label className="slider">
        <span>Громкость — {Math.round(settings.volume * 100)}%</span>
        <input type="range" min={0} max={1} step={0.01} value={settings.volume} onChange={(e) => onChange({ volume: Number(e.target.value) })} />
      </label>
      <label className="slider">
        <span>Реверберация (эхо помещения) — {Math.round(settings.reverb * 100)}%</span>
        <input type="range" min={0} max={1} step={0.01} value={settings.reverb} onChange={(e) => onChange({ reverb: Number(e.target.value) })} />
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
        Играть аккорд после каждого изменения на грифе
      </label>
    </div>
  );
}
