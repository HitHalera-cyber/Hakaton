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

const PLAY_MODES: [PlayMode, string, string][] = [
  ['strum', '↓ Бой вниз', 'Удар по струнам сверху вниз (от баса)'],
  ['strumUp', '↑ Бой вверх', 'Удар снизу вверх (от тонких струн)'],
  ['arpeggio', '♪ Перебор', 'Струны по одной'],
];

interface Props {
  settings: SoundSettings;
  instrument: Instrument;
  onChange: (patch: Partial<SoundSettings>) => void;
  /** Сыграть аккорд выбранным способом (для пробы). */
  onPlay: (mode: PlayMode) => void;
  onStop: () => void;
  canPlay: boolean;
}

export function SoundPanel({ settings, instrument, onChange, onPlay, onStop, canPlay }: Props) {
  return (
    <div className="tab-body">
      <p className="hint">Выберите, как звучит аккорд — выбор запоминается для кнопки «Играть» и для автоигры, пока вы его не смените.</p>
      <div className="row">
        <div className="segmented" role="radiogroup" aria-label="Как играть аккорд">
          {PLAY_MODES.map(([mode, label, title]) => (
            <button
              key={mode}
              className={settings.mode === mode ? 'on' : ''}
              title={title}
              onClick={() => {
                onChange({ mode });
                if (canPlay) onPlay(mode);
              }}
            >
              {label}
            </button>
          ))}
        </div>
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
        Играть аккорд после каждого изменения на грифе
      </label>
    </div>
  );
}
