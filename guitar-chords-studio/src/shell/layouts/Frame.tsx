import type { ReactNode } from 'react';
import type { ModuleId } from '../../modules/ids';
import { usePick } from '../../store';
import { Drawer } from '../ModuleSection';
import { Sidebar } from '../Sidebar';
import { TopBar } from '../TopBar';

/** Каркас раскладки: меню (полное или полоса иконок), верхняя панель, рабочая область и выдвижная панель. */
export function Frame({
  compact,
  active,
  onOpen,
  children,
}: {
  compact?: boolean;
  active: ModuleId | null;
  onOpen: (id: ModuleId) => void;
  children: ReactNode;
}) {
  const { drawerOpen, tab, closeDrawer } = usePick((s) => ({
    drawerOpen: s.drawerOpen,
    tab: s.settings.view.tab,
    closeDrawer: s.closeDrawer,
  }));
  return (
    <>
      <Sidebar compact={compact} active={active} onOpen={onOpen} />
      <div className="main">
        <TopBar />
        {children}
      </div>
      {compact && drawerOpen && <Drawer id={tab} onClose={closeDrawer} />}
    </>
  );
}
