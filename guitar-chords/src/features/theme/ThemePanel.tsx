import './theme.css';
import { THEMES, type ThemeId } from '../../app/themes';

interface Props {
  current: ThemeId;
  onChange: (t: ThemeId) => void;
}

/** Выбор темы: карточки-превью с цветами и шрифтом каждой темы. */
export function ThemePanel({ current, onChange }: Props) {
  return (
    <div className="tab-body">
      <p className="hint">Тема меняет цвета, шрифты, форму кнопок и вид грифа. Выбор сохраняется.</p>
      <div className="theme-grid">
        {THEMES.map((t) => (
          <button key={t.id} className={`theme-card ${t.id === current ? 'on' : ''}`} data-theme={t.id} onClick={() => onChange(t.id)}>
            <span className="theme-swatches">
              {t.swatch.map((c, i) => (
                <span key={i} style={{ background: c }} />
              ))}
            </span>
            <b>{t.name}</b>
            <small>{t.description}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
