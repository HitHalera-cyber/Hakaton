import { UpdateBanner } from '../../features/about/Updates';
import { useApp } from '../AppContext';
import { BoardCard } from './BoardCard';
import { ChordCard, navBadges, ToolSection } from './common';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

/** «Классика»: меню слева, гриф сверху, под ним аккорд и выбранный раздел. */
export function ClassicLayout() {
  const app = useApp();
  const tab = app.settings.view.tab;
  return (
    <>
      <Sidebar tab={tab} onTab={app.openTab} onAbout={() => app.setAboutOpen(true)} badges={navBadges(app)} />
      <div className="main">
        <UpdateBanner status={app.updates.status} />
        <TopBar />
        <main className="workspace classic">
          <BoardCard />
          <ChordCard />
          <ToolSection tab={tab} />
        </main>
      </div>
    </>
  );
}
