import { AboutDialog } from '../features/about/Updates';
import { AppProvider, useApp } from './AppContext';
import { ClassicLayout } from './layout/ClassicLayout';
import { DashboardLayout } from './layout/DashboardLayout';
import { FreeLayout } from './layout/FreeLayout';
import { ListenerLayout } from './layout/ListenerLayout';
import type { LayoutId } from './layouts';

const LAYOUT_VIEWS: Record<LayoutId, () => React.JSX.Element> = {
  classic: ClassicLayout,
  dashboard: DashboardLayout,
  listener: ListenerLayout,
  free: FreeLayout,
};

function Shell() {
  const app = useApp();
  const layout = app.settings.view.layout;
  const View = LAYOUT_VIEWS[layout] ?? ClassicLayout;
  return (
    <div className={`app layout-${layout}`}>
      <View />
      {app.toast && <div className="toast">{app.toast}</div>}
      {app.aboutOpen && <AboutDialog info={app.updates.info} status={app.updates.status} onClose={() => app.setAboutOpen(false)} />}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
