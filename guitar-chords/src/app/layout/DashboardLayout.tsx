import { useApp } from '../AppContext';
import { ALL_TABS, type TabId } from '../navigation';
import { ToolPanel } from '../panels';
import { BoardCard } from './BoardCard';
import { ChordCard, Drawer, RailFrame } from './common';
import { useDrawer } from './useDrawer';

/** «Приборная панель»: гриф, аккорд и четыре плитки с разделами на одном экране. */
export function DashboardLayout() {
  const { settings } = useApp();
  const drawer = useDrawer();
  const { tiles } = settings.view;
  const setTile = (i: number, tab: TabId) => settings.patchView({ tiles: tiles.map((t, j) => (j === i ? tab : t)) });

  return (
    <RailFrame active={drawer.tab} onNav={drawer.show}>
      <main className="workspace dashboard">
        <BoardCard />
        <ChordCard />
        {tiles.map((tab, i) => (
          <section key={`${i}-${tab}`} className={`panel tile tile-${i}`}>
            <h2 className="tool-title">
              <span>{ALL_TABS.find((t) => t.id === tab)!.icon}</span>
              <select
                className="tile-select"
                value={tab}
                onChange={(e) => setTile(i, e.target.value as TabId)}
                title="Что показывать в плитке"
              >
                {ALL_TABS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </h2>
            <div className="tile-body">
              <ToolPanel tab={tab} />
            </div>
          </section>
        ))}
      </main>
      {drawer.tab && <Drawer tab={drawer.tab} onClose={drawer.close} />}
    </RailFrame>
  );
}
