import { useEffect } from 'react';
import { startServices } from '../services/wiring';
import { usePick } from '../store';
import type { LayoutId } from '../store/model';
import { AboutDialog } from './About';
import { CommandPalette } from './CommandPalette';
import { ClassicLayout } from './layouts/Classic';
import { DashboardLayout } from './layouts/Dashboard';
import { FreeLayout } from './layouts/Free';
import { ListenerLayout } from './layouts/Listener';

const LAYOUT_VIEWS: Record<LayoutId, () => React.JSX.Element> = {
  classic: ClassicLayout,
  dashboard: DashboardLayout,
  listener: ListenerLayout,
  free: FreeLayout,
};

export default function App() {
  const { layout, toastText } = usePick((s) => ({ layout: s.settings.view.layout, toastText: s.toastText }));
  useEffect(startServices, []);
  const View = LAYOUT_VIEWS[layout] ?? ClassicLayout;
  return (
    <div className={`app layout-${layout}`}>
      <View />
      {toastText && <div className="toast">{toastText}</div>}
      <CommandPalette />
      <AboutDialog />
    </div>
  );
}
