import { useEffect } from 'react';
import { startServices } from '../services/wiring';
import { usePick } from '../store';
import type { LayoutId } from '../store/model';
import { AboutDialog } from './About';
import { CommandPalette } from './CommandPalette';
import { ClassicLayout } from './layouts/Classic';
import { DashboardLayout } from './layouts/Dashboard';
import { ListenerLayout } from './layouts/Listener';
import { PhoneLayout } from './layouts/Phone';
import { usePhone } from './usePhone';

const LAYOUT_VIEWS: Record<LayoutId, () => React.JSX.Element> = {
  classic: ClassicLayout,
  dashboard: DashboardLayout,
  listener: ListenerLayout,
};

export default function App() {
  const { layout, toastText } = usePick((s) => ({ layout: s.settings.view.layout, toastText: s.toastText }));
  useEffect(startServices, []);
  // На телефоне — всегда своя раскладка, выбранная на компьютере не меняется.
  const phone = usePhone();
  const View = phone ? PhoneLayout : (LAYOUT_VIEWS[layout] ?? ClassicLayout);
  return (
    <div className={`app layout-${phone ? 'phone' : layout}`}>
      <View />
      {toastText && <div className="toast">{toastText}</div>}
      <CommandPalette />
      <AboutDialog />
    </div>
  );
}
