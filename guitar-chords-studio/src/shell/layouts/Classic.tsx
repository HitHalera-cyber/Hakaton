import { store, usePick } from '../../store';
import { BoardCard } from '../BoardCard';
import { ChordCard } from '../ChordCard';
import { ModuleSection } from '../ModuleSection';
import { Frame } from './Frame';

/** «Классика»: меню слева, гриф сверху, под ним аккорд и выбранный раздел. */
export function ClassicLayout() {
  const tab = usePick((s) => s.settings.view.tab);
  return (
    <Frame active={tab} onOpen={(id) => store.getState().openModule(id)}>
      <main className="workspace classic">
        <BoardCard />
        <ChordCard />
        <ModuleSection id={tab} />
      </main>
    </Frame>
  );
}
