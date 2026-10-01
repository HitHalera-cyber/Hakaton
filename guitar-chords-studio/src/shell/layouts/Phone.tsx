import { useEffect, useRef, useState } from 'react';
import { getModule } from '../../modules/registry';
import { store, usePick } from '../../store';
import { BoardCard } from '../BoardCard';
import { ChordCard } from '../ChordCard';
import { ModuleSection } from '../ModuleSection';
import { Sidebar } from '../Sidebar';
import { TopBar } from '../TopBar';

/**
 * Телефон: сверху полоса с кнопкой меню (☰), названием раздела и настройками (⚙).
 * Меню и настройки выезжают поверх; ниже — гриф (прокручивается пальцем), аккорд и раздел.
 */
export function PhoneLayout() {
  const tab = usePick((s) => s.settings.view.tab);
  const [menu, setMenu] = useState(false);
  const [settings, setSettings] = useState(false);
  const section = useRef<HTMLDivElement>(null);
  const m = getModule(tab);

  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenu(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menu]);

  return (
    <div className="main phone-main">
      <header className="phone-bar">
        <button className="btn phone-btn" onClick={() => setMenu(true)} aria-label="Меню разделов">
          ☰
        </button>
        <button className="phone-title" onClick={() => section.current?.scrollIntoView({ behavior: 'smooth' })} title="К разделу">
          {m.icon} {m.title}
        </button>
        <button className={`btn phone-btn ${settings ? 'on' : ''}`} onClick={() => setSettings((v) => !v)} aria-label="Настройки грифа">
          ⚙
        </button>
      </header>
      {settings && (
        <div className="phone-settings">
          <TopBar />
        </div>
      )}
      <main className="workspace phone">
        <BoardCard />
        <ChordCard />
        <div ref={section}>
          <ModuleSection id={tab} />
        </div>
      </main>
      {menu && (
        <>
          <div className="drawer-backdrop" onClick={() => setMenu(false)} />
          <div className="phone-menu">
            <Sidebar
              active={tab}
              onOpen={(id) => {
                store.getState().patchView({ tab: id });
                setMenu(false);
                window.setTimeout(() => section.current?.scrollIntoView({ behavior: 'smooth' }), 50);
              }}
            />
          </div>
        </>
      )}
    </div>
  );
}
