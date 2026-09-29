import { pcName } from '../../core/music/notes';
import { SCALES, scaleNoteNames } from '../../core/music/scales';

export interface ScaleSettings {
  show: boolean;
  rootPc: number;
  scaleId: string;
}

interface Props {
  settings: ScaleSettings;
  onChange: (patch: Partial<ScaleSettings>) => void;
  onPlay: (steps: number[], rootPc: number) => void;
}

export function ScalesPanel({ settings, onChange, onPlay }: Props) {
  const scale = SCALES.find((s) => s.id === settings.scaleId) ?? SCALES[0];
  const names = scaleNoteNames(settings.rootPc, scale);

  return (
    <div className="tab-body">
      <label className="check big">
        <input type="checkbox" checked={settings.show} onChange={(e) => onChange({ show: e.target.checked })} />
        Показать гамму на грифе
      </label>

      <div className="root-picker">
        {Array.from({ length: 12 }, (_, pc) => (
          <button key={pc} className={pc === settings.rootPc ? 'on' : ''} onClick={() => onChange({ rootPc: pc, show: true })}>
            {pcName(pc)}
          </button>
        ))}
      </div>
      <label className="field">
        <span>Гамма / лад</span>
        <select value={scale.id} onChange={(e) => onChange({ scaleId: e.target.value, show: true })}>
          {SCALES.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <div className="scale-notes">
        {names.map((n, i) => (
          <span key={i} className={i === 0 ? 'root' : ''}>
            <b>{n}</b>
            <small>{scale.degrees[i]}</small>
          </span>
        ))}
      </div>

      <div className="row">
        <button className="btn primary" onClick={() => onPlay(scale.steps, settings.rootPc)}>
          ▶ Проиграть гамму
        </button>
      </div>
      <p className="hint">
        Тоника гаммы — оранжевые кружки, остальные ноты — жёлтые. Переключатель «В точках: ступени» в верхней панели показывает номера
        ступеней вместо названий нот. Для импровизации: минорная пентатоника — самый популярный вариант для рока и блюза.
      </p>
    </div>
  );
}
