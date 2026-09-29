// Контроллер приложения: собирает состояние из хуков и раздаёт его панелям через контекст.
// Панели в features/ ничего не знают друг о друге — связи между ними живут только здесь.

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { audio } from '../core/audio/engine';
import { boardFromFrets, type Board, type Frets } from '../core/music/fretboard';
import type { ChordRef } from '../features/library/LibraryPanel';
import { useChordListener } from '../features/listen/useChordListener';
import { useSequencer, type SeqItem } from '../features/sequencer/useSequencer';
import { useUpdates } from '../features/about/Updates';
import type { TabId } from './navigation';
import { uid, useSettings } from './settings';
import { useCircleTrail } from './useCircleTrail';
import { useCollections } from './useCollections';
import { useExports } from './useExports';
import { useGuitar } from './useGuitar';
import { useMidiIO } from './useMidiIO';
import { useStored } from './useStored';

function useToast() {
  const [toast, setToast] = useState<string | null>(null);
  const show = useCallback((text: string) => {
    setToast(text);
    window.setTimeout(() => setToast((t) => (t === text ? null : t)), 2600);
  }, []);
  return { toast, show };
}

function useAppController() {
  const settings = useSettings();
  const { toast, show: showToast } = useToast();
  const midi = useMidiIO();
  const guitar = useGuitar(settings, midi, showToast);
  const collections = useCollections(settings, guitar, showToast);
  const circle = useCircleTrail(guitar);
  const exports = useExports(settings, guitar, showToast);
  const updates = useUpdates();
  const [aboutOpen, setAboutOpen] = useState(false);
  const [libRequest, setLibRequest] = useState<{ ref: ChordRef; nonce: number } | null>(null);
  const openTab = useCallback((tab: TabId) => settings.patchView({ tab }), [settings]);

  // ---------- Последовательность ----------
  const [sequence, setSequence] = useStored<SeqItem[]>('gc.sequence', []);
  const sequencer = useSequencer(sequence, settings.rhythm, (item) => {
    if (item.strings.length === guitar.strings.length) guitar.setBoard(item.board);
  });
  const makeItem = (symbol: string, board: Board, beats = 4): SeqItem => ({
    id: uid(),
    symbol,
    board,
    strings: guitar.strings,
    capo: guitar.capo,
    beats,
  });
  const itemsFromFrets = (chords: { symbol: string; frets: Frets; beats?: number }[]) =>
    chords.map((c) => makeItem(c.symbol, boardFromFrets(c.frets, guitar.capo), c.beats));
  const addCurrentToSequence = () => {
    setSequence((list) => [...list, makeItem(guitar.currentSymbol(), guitar.currentBoard())]);
    showToast(`«${guitar.currentSymbol()}» добавлен в последовательность`);
  };

  // ---------- Гитара через микрофон ----------
  // Пока играет разбираемая песня, микрофон слышит колонки — его аккорды гриф не трогают.
  const [songPlaying, setSongPlaying] = useState(false);
  const songPlayingRef = useRef(false);
  songPlayingRef.current = songPlaying;
  const showOnBoardRef = useRef(true);
  const listener = useChordListener((c) => {
    if (songPlayingRef.current) return;
    circle.push({ rootPc: c.rootPc, templateId: c.templateId, symbol: c.symbol, nameRu: c.nameRu, source: 'guitar' });
    if (showOnBoardRef.current) guitar.showChord(c.rootPc, c.templateId, c.bassPc);
  });
  showOnBoardRef.current = listener.showOnBoard;

  // ---------- Горячие клавиши ----------
  const hot = useRef({ guitar, sequencer });
  hot.current = { guitar, sequencer };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      const { guitar: g, sequencer: s } = hot.current;
      if (e.code === 'Space') {
        e.preventDefault();
        g.play();
      } else if (e.key === 'Escape') {
        audio.stopAll();
        s.stop();
      } else if (e.key === 'Delete' || e.key === 'Backspace') g.clear();
      else if (e.key === 'ArrowRight') g.transpose(1);
      else if (e.key === 'ArrowLeft') g.transpose(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // ---------- Тема и перетаскивание файлов ----------
  useEffect(() => {
    document.documentElement.dataset.theme = settings.view.theme;
  }, [settings.view.theme]);
  useEffect(() => {
    // Файл, брошенный мимо зоны разбора песни, не должен открываться вместо программы.
    const prevent = (e: DragEvent) => e.preventDefault();
    window.addEventListener('dragover', prevent);
    window.addEventListener('drop', prevent);
    return () => {
      window.removeEventListener('dragover', prevent);
      window.removeEventListener('drop', prevent);
    };
  }, []);

  return {
    settings,
    toast,
    showToast,
    midi,
    guitar,
    collections,
    circle,
    exports,
    updates,
    aboutOpen,
    setAboutOpen,
    libRequest,
    showVoicings: (ref: ChordRef) => {
      setLibRequest({ ref, nonce: Date.now() });
      openTab('library');
    },
    openTab,
    sequence,
    setSequence,
    sequencer,
    itemsFromFrets,
    addCurrentToSequence,
    listener,
    songPlaying,
    setSongPlaying,
  };
}

export type App = ReturnType<typeof useAppController>;

const Ctx = createContext<App | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const app = useAppController();
  return <Ctx.Provider value={app}>{children}</Ctx.Provider>;
}

export function useApp(): App {
  const app = useContext(Ctx);
  if (!app) throw new Error('useApp() вне <AppProvider>');
  return app;
}
