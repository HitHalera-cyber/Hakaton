import { useState } from 'react';
import { MODULE_HELP } from '../modules/help';
import { MODULE_GROUPS, getModule } from '../modules/registry';
import { HelpPopover } from './HelpPopover';
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
  const [help, setHelp] = useState<{ id: ModuleId; x: number; y: number } | null>(null);
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
                onContextMenu={(e) => {
                  e.preventDefault();
                  setHelp({ id: m.id, x: e.clientX, y: e.clientY });
                }}
                title={`${compact ? m.title : m.description} · правый клик — подробнее`}
              >
                <span className="nav-icon">{m.icon}</span>
                <span className="nav-label">{m.title}</span>
                {badges[m.id] && <span className="nav-badge">{badges[m.id]}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <button className="nav-item about" onClick={() => setAboutOpen(true)} title={compact ? 'О программе' : undefined}>
        <span className="nav-icon">ℹ</span>
        <span className="nav-label">О программе</span>
      </button>
      {help && (
        <HelpPopover
          {...help}
          icon={getModule(help.id).icon}
          title={getModule(help.id).title}
          text={MODULE_HELP[help.id]}
          onClose={() => setHelp(null)}
        />
      )}
    </aside>
  );
}
