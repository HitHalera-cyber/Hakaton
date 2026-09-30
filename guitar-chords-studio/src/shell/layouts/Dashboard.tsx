import { MODULES, getModule } from '../../modules/registry';
import type { ModuleId } from '../../modules/ids';
import { store, usePick } from '../../store';
import { BoardCard } from '../BoardCard';
import { ChordCard } from '../ChordCard';
import { Frame } from './Frame';

/** «Приборная панель»: гриф, аккорд и четыре плитки с разделами на одном экране. */
export function DashboardLayout() {
  const { tiles, patchView, drawerOpen, tab } = usePick((s) => ({
    tiles: s.settings.view.tiles,
    patchView: s.patchView,
    drawerOpen: s.drawerOpen,
    tab: s.settings.view.tab,
  }));
  const setTile = (i: number, id: ModuleId) => patchView({ tiles: tiles.map((t, j) => (j === i ? id : t)) });
  return (
    <Frame compact active={drawerOpen ? tab : null} onOpen={(id) => store.getState().openModule(id)}>
      <main className={`workspace dashboard ${tiles.includes('circle') ? 'has-circle' : ''}`}>
        <BoardCard />
        <ChordCard />
        {tiles.map((id, i) => {
          const m = getModule(id);
          return (
            <section key={`${i}-${id}`} className={`panel tile tile-${i}`}>
              <h2 className="tool-title">
                <span>{m.icon}</span>
                <select
                  className="tile-select"
                  value={id}
                  onChange={(e) => setTile(i, e.target.value as ModuleId)}
                  title="Что показывать в плитке"
                >
                  {MODULES.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.title}
                    </option>
                  ))}
                </select>
              </h2>
              <div className="tile-body">
                <m.View />
              </div>
            </section>
          );
        })}
      </main>
    </Frame>
  );
}
