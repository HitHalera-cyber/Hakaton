import { HistoryPanel, SavedPanel, type HistoryEntry, type SavedShape } from './SidePanels';

interface Collections {
  saved: SavedShape[];
  openSaved: (s: SavedShape) => void;
  removeSaved: (id: string) => void;
  renameSaved: (id: string, name: string) => void;
  exportSaved: () => void;
  importSaved: () => void;
  history: HistoryEntry[];
  openHistory: (h: HistoryEntry) => void;
  clearHistory: () => void;
}

/** Избранные аппликатуры и история — рядом, в одном разделе. */
export function FavoritesTab({ collections: c }: { collections: Collections }) {
  return (
    <div className="favorites-tab">
      <SavedPanel
        items={c.saved}
        onPick={c.openSaved}
        onDelete={c.removeSaved}
        onRename={c.renameSaved}
        onExport={c.exportSaved}
        onImport={c.importSaved}
      />
      <HistoryPanel items={c.history} onPick={c.openHistory} onClear={c.clearHistory} />
    </div>
  );
}
