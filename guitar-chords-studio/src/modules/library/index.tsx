import { store, useGuitar, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { LibraryPanel } from './LibraryPanel';

function LibraryView() {
  const g = useGuitar();
  const { libRequest } = usePick((s) => ({ libRequest: s.libRequest }));
  const request = libRequest ? { ref: libRequest, nonce: libRequest.nonce } : null;
  return (
    <LibraryPanel
      tuning={g.strings}
      capo={g.capo}
      current={g.chordRef}
      request={request}
      onPick={(frets) => store.getState().loadFrets(frets)}
    />
  );
}

export const libraryModule: ModuleDef = {
  id: 'library',
  title: 'Справочник',
  icon: '📖',
  group: 'learn',
  description: 'Все аккорды и их аппликатуры с поиском по названию',
  keywords: ['аппликатура', 'поиск', 'аккорды'],
  View: LibraryView,
};
