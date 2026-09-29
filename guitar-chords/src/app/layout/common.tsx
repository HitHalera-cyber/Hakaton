// Общие части раскладок: карточка аккорда, раздел с заголовком, полоса иконок и выдвижная панель.

import { useEffect, type ReactNode } from 'react';
import { UpdateBanner } from '../../features/about/Updates';
import { ChordDisplay } from '../../features/chord/ChordDisplay';
import { useApp, type App } from '../AppContext';
import { ALL_TABS, type TabId } from '../navigation';
import { ToolPanel } from '../panels';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export const tabInfo = (tab: TabId) => ALL_TABS.find((t) => t.id === tab)!;

export const navBadges = (app: App) => ({
  sequence: app.sequencer.playing ? '▶' : undefined,
  listen: app.listener.active ? '●' : undefined,
});

/** Текущий аккорд: название, состав, кнопки «играть», «в избранное», экспорт. */
export function ChordCard() {
  const app = useApp();
  const { guitar } = app;
  return (
    <ChordDisplay
      result={guitar.result}
      soundingMidi={guitar.activeMidi}
      source={guitar.source}
      capo={guitar.capo}
      shapeSymbol={guitar.shapeSymbol}
      warnings={guitar.source === 'board' ? guitar.fingering.warnings : []}
      onPlay={guitar.play}
      onSave={app.collections.save}
      onAddToSequence={app.addCurrentToSequence}
      onShowVoicings={guitar.chordRef ? () => app.showVoicings(guitar.chordRef!) : undefined}
      onExport={app.exports.exportChord}
    />
  );
}

/** Раздел программы в карточке с заголовком. */
export function ToolSection({ tab, className = '', onClose }: { tab: TabId; className?: string; onClose?: () => void }) {
  const t = tabInfo(tab);
  return (
    <section className={`panel tools ${className}`}>
      <h2 className="tool-title">
        <span>{t.icon}</span> {t.label}
        {onClose && (
          <button className="btn small close" onClick={onClose} title="Закрыть (Esc)">
            ✕
          </button>
        )}
      </h2>
      <ToolPanel tab={tab} />
    </section>
  );
}

/** Выдвижная панель справа — в раскладках без постоянной области для раздела. */
export function Drawer({ tab, onClose }: { tab: TabId; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        <ToolSection tab={tab} onClose={onClose} />
      </aside>
    </>
  );
}

/** Каркас раскладок с узкой полосой иконок вместо бокового меню. */
export function RailFrame({ active, onNav, children }: { active: TabId | null; onNav: (tab: TabId) => void; children: ReactNode }) {
  const app = useApp();
  return (
    <>
      <Sidebar compact tab={active} onTab={onNav} onAbout={() => app.setAboutOpen(true)} badges={navBadges(app)} />
      <div className="main">
        <UpdateBanner status={app.updates.status} />
        <TopBar />
        {children}
      </div>
    </>
  );
}
