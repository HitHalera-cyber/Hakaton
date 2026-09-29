import { NAV_GROUPS, type TabId } from '../navigation';

interface Props {
  tab: TabId;
  onTab: (t: TabId) => void;
  onAbout: () => void;
  /** Отметки на пунктах меню: «играет», «слушает». */
  badges: Partial<Record<TabId, string>>;
}

export function Sidebar({ tab, onTab, onAbout, badges }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="logo">🎸</span>
        <div>
          <h1>Гитарные аккорды</h1>
          <p>гриф · звук · слух</p>
        </div>
      </div>
      <nav className="nav">
        {NAV_GROUPS.map((g) => (
          <div key={g.title} className="nav-group">
            <div className="nav-title">{g.title}</div>
            {g.items.map((it) => (
              <button key={it.id} className={`nav-item ${tab === it.id ? 'on' : ''}`} onClick={() => onTab(it.id)}>
                <span className="nav-icon">{it.icon}</span>
                <span className="nav-label">{it.label}</span>
                {badges[it.id] && <span className="nav-badge">{badges[it.id]}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <button className="nav-item about" onClick={onAbout}>
        <span className="nav-icon">ℹ</span>
        <span className="nav-label">О программе</span>
      </button>
    </aside>
  );
}
