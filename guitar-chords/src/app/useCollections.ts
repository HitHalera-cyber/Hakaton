// История аккордов и избранные аппликатуры (с экспортом/импортом в JSON).

import { useEffect } from 'react';
import { pickFile, saveFile } from '../core/export/download';
import { boardFromMidi } from '../core/music/fretboard';
import type { HistoryEntry, SavedShape } from '../features/favorites/SidePanels';
import { normalizeShape, uid, type Settings } from './settings';
import type { Guitar } from './useGuitar';
import { useStored } from './useStored';

const HISTORY_LIMIT = 40;

export function useCollections(settings: Settings, guitar: Guitar, toast: (text: string) => void) {
  const [history, setHistory] = useStored<HistoryEntry[]>('gc.history', []);
  const [saved, setSaved] = useStored<SavedShape[]>('gc.saved', []);
  const { result, source, board, activeMidi, strings, capo } = guitar;

  useEffect(() => {
    setSaved((list) => list.map(normalizeShape));
    setHistory((list) => list.map(normalizeShape));
  }, []);

  // В историю попадает аккорд, который «устоялся» (не менялся ~0,8 с).
  useEffect(() => {
    if (result.kind !== 'chord' || !result.primary) return;
    const p = result.primary;
    const t = setTimeout(() => {
      setHistory((h) => {
        if (h[0]?.symbol === p.symbol) return h;
        const entry: HistoryEntry = {
          id: uid(),
          symbol: p.symbol,
          nameRu: p.nameRu + (p.inversionRu ? `, ${p.inversionRu}` : ''),
          notes: result.noteNames,
          time: Date.now(),
          source,
          tuning: settings.view.tuning,
          strings,
          capo,
          board: source === 'board' ? board : undefined,
          midi: source === 'midi' ? activeMidi : undefined,
        };
        return [entry, ...h].slice(0, HISTORY_LIMIT);
      });
    }, 800);
    return () => clearTimeout(t);
  }, [result]);

  const save = () => {
    const symbol = guitar.currentSymbol();
    setSaved((s) => [
      {
        id: uid(),
        name: symbol,
        symbol,
        nameRu: result.primary ? result.primary.nameRu : 'Неизвестный аккорд',
        tuning: settings.view.tuning,
        strings,
        capo,
        board: guitar.currentBoard(),
        created: Date.now(),
      },
      ...s,
    ]);
    toast(`«${symbol}» добавлен в избранное`);
  };

  const openSaved = (s: SavedShape) => {
    const n = normalizeShape(s);
    guitar.loadShape(n.board, n.tuning, n.strings, n.capo);
  };

  const openHistory = (h: HistoryEntry) => {
    const e = normalizeShape(h);
    if (e.board) guitar.loadShape(e.board, e.tuning, e.strings, e.capo);
    else if (e.midi) guitar.loadShape(boardFromMidi(e.midi, e.strings, e.capo), e.tuning, e.strings, e.capo);
  };

  const exportSaved = () =>
    saveFile(JSON.stringify({ app: 'GuitarChords', version: 1, saved }, null, 2), 'favorites.json', 'application/json');

  const importSaved = async () => {
    const file = await pickFile('.json,application/json');
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const list = (Array.isArray(data) ? data : data.saved) as SavedShape[];
      if (!Array.isArray(list)) throw new Error();
      const valid = list.filter((s) => s && Array.isArray(s.board) && typeof s.symbol === 'string').map(normalizeShape);
      setSaved((cur) => {
        const ids = new Set(cur.map((s) => s.id));
        return [...cur, ...valid.filter((s) => !ids.has(s.id))];
      });
      toast(`Загружено аппликатур: ${valid.length}`);
    } catch {
      toast('Не удалось прочитать файл избранного');
    }
  };

  return {
    history,
    clearHistory: () => setHistory([]),
    openHistory,
    saved,
    save,
    openSaved,
    removeSaved: (id: string) => setSaved((list) => list.filter((s) => s.id !== id)),
    renameSaved: (id: string, name: string) => setSaved((list) => list.map((s) => (s.id === id ? { ...s, name } : s))),
    exportSaved,
    importSaved: () => void importSaved(),
  };
}
