import { useCallback, useState } from 'react';
import { useApp } from '../AppContext';
import type { TabId } from '../navigation';

/** Раздел в выдвижной панели: открывается кликом по иконке, закрывается ✕, Esc или кликом мимо. */
export function useDrawer() {
  const app = useApp();
  const [open, setOpen] = useState(false);
  const show = useCallback(
    (tab: TabId) => {
      app.openTab(tab);
      setOpen(true);
    },
    [app.openTab],
  );
  const close = useCallback(() => setOpen(false), []);
  return { tab: open ? app.settings.view.tab : null, show, close };
}
