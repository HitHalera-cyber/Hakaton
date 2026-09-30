import { pickFile, saveFile } from '../../core/export/download';
import type { SavedShape } from '../../store/model';
import { store, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { FavoritesTab } from './FavoritesTab';

async function importSaved() {
  const file = await pickFile('.json,application/json');
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    const list = (Array.isArray(data) ? data : data.saved) as SavedShape[];
    if (!Array.isArray(list)) throw new Error();
    store.getState().toast(`Загружено аппликатур: ${store.getState().importSaved(list)}`);
  } catch {
    store.getState().toast('Не удалось прочитать файл избранного');
  }
}

function FavoritesView() {
  const s = usePick((s) => ({
    saved: s.saved,
    history: s.history,
    openShape: s.openShape,
    removeSaved: s.removeSaved,
    renameSaved: s.renameSaved,
    clearHistory: s.clearHistory,
  }));
  return (
    <FavoritesTab
      collections={{
        saved: s.saved,
        openSaved: s.openShape,
        removeSaved: s.removeSaved,
        renameSaved: s.renameSaved,
        exportSaved: () =>
          saveFile(JSON.stringify({ app: 'GuitarChords', version: 1, saved: s.saved }, null, 2), 'favorites.json', 'application/json'),
        importSaved: () => void importSaved(),
        history: s.history,
        openHistory: s.openShape,
        clearHistory: s.clearHistory,
      }}
    />
  );
}

export const favoritesModule: ModuleDef = {
  id: 'favorites',
  title: 'Избранное и история',
  icon: '⭐',
  group: 'tools',
  description: 'Сохранённые аппликатуры и история аккордов',
  keywords: ['сохранить', 'история', 'импорт', 'экспорт'],
  View: FavoritesView,
};
