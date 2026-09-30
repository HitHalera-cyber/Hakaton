import { MODULE_GROUPS } from '../modules/registry';
import type { ModuleId } from '../modules/ids';
import { usePick } from '../store';

interface Props {
  /** Подсвеченный раздел (null — ничего не подсвечивать). */
  active: ModuleId | null;
  /** Узкая полоса из одних иконок. */
  compact?: boolean;
  onOpen: (id: ModuleId) => void;
}

/** Меню разделов — строится по реестру модулей. */
export function Sidebar({ active, compact, onOpen }: Props) {
  const { listening, seqPlaying, setAboutOpen, setPaletteOpen } = usePick((s) => ({
    listening: s.listen.active,
    seqPlaying: s.seq.playing,
    setAboutOpen: s.setAboutOpen,
    setPaletteOpen: s.setPaletteOpen,
  }));
  const badges: Partial<Record<ModuleId, string>> = { sequence: seqPlaying ? '▶' : undefined, listen: listening ? '●' : undefined };
  return (
    <aside className={`sidebar ${compact ? 'compact' : ''}`}>
      <div className="brand">
        <span className="logo">🎸</span>
        <div>
          <h1>Гитарные аккорды</h1>
          <p>Studio</p>
        </div>
      </div>
      <button className="nav-item search" onClick={() => setPaletteOpen(true)} title="Найти раздел, аккорд или песню (Ctrl+K)">
        <span className="nav-icon">🔍</span>
        <span className="nav-label">Поиск</span>
        <kbd className="nav-label">Ctrl K</kbd>
      </button>
      <nav className="nav">
        {MODULE_GROUPS.map((g) => (
          <div key={g.id} className="nav-group">
            <div className="nav-title">{g.title}</div>
            {g.modules.map((m) => (
              <button
                key={m.id}
                className={`nav-item ${active === m.id ? 'on' : ''}`}
                onClick={() => onOpen(m.id)}
                title={compact ? m.title : m.description}
              >
                <span className="nav-icon">{m.icon}</span>
                <span className="nav-label">{m.title}</span>
                {badges[m.id] ? (
                  <span className="nav-badge">{badges[m.id]}</span>
                ) : (
                  m.isNew && <span className="nav-new" title="Новое в Studio" />
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <button className="nav-item about" onClick={() => setAboutOpen(true)} title={compact ? 'О программе' : undefined}>
        <span className="nav-icon">ℹ</span>
        <span className="nav-label">О программе</span>
      </button>
    </aside>
  );
}
