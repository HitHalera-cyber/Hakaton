import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { synth } from './audio/guitarSynth';
import { ChordDisplay } from './components/ChordDisplay';
import { Fretboard, type DotLabel, type Orientation } from './components/Fretboard';
import { MidiPanel, type MidiStatus } from './components/MidiPanel';
import { HistoryPanel, SavedPanel, type HistoryEntry, type SavedShape } from './components/SidePanels';
import { SoundPanel, type SoundSettings } from './components/SoundPanel';
import { ALL_DEVICES, MidiInput, type MidiDevice } from './midi/midiInput';
import { detectChord } from './music/chords';
import {
  boardFromMidi,
  cycleNut,
  emptyBoard,
  guitarRange,
  isBoardEmpty,
  setNut,
  soundingNotes,
  toggleFret,
  type Board,
} from './music/fretboard';
import { TUNINGS, type TuningId } from './music/tunings';
import { useStored } from './state/useStored';

interface ViewSettings {
  theme: 'dark' | 'light';
  orientation: Orientation;
  showNotes: boolean;
  dotLabel: DotLabel;
  realistic: boolean;
  tuning: TuningId;
}

const DEFAULT_VIEW: ViewSettings = {
  theme: 'dark',
  orientation: 'horizontal',
  showNotes: false,
  dotLabel: 'note',
  realistic: true,
  tuning: 'standard',
};

const DEFAULT_SOUND: SoundSettings = { volume: 0.8, mode: 'strum', arpStepMs: 180, timbre: 'acoustic', autoPlay: true };

const HISTORY_LIMIT = 40;
const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

export default function App() {
  const [view, setView] = useStored<ViewSettings>('gc.view', DEFAULT_VIEW);
  const [sound, setSound] = useStored<SoundSettings>('gc.sound', DEFAULT_SOUND);
  const [board, setBoard] = useStored<Board>('gc.board', emptyBoard());
  const [history, setHistory] = useStored<HistoryEntry[]>('gc.history', []);
  const [saved, setSaved] = useStored<SavedShape[]>('gc.saved', []);
  const [midiOpts, setMidiOpts] = useStored('gc.midi', { latch: true, sound: true, device: ALL_DEVICES });

  const tuning = TUNINGS[view.tuning].strings;
  const range = useMemo(() => guitarRange(tuning), [tuning]);

  // ---------- Звук ----------
  useEffect(() => synth.setVolume(sound.volume), [sound.volume]);
  useEffect(() => synth.setTimbre(sound.timbre), [sound.timbre]);

  const playMidi = useCallback(
    (notes: number[]) => synth.playChord(notes, sound.mode, sound.arpStepMs),
    [sound.mode, sound.arpStepMs],
  );

  // ---------- MIDI ----------
  const [midiStatus, setMidiStatus] = useState<MidiStatus>('init');
  const [midiError, setMidiError] = useState<string>();
  const [devices, setDevices] = useState<MidiDevice[]>([]);
  const [held, setHeld] = useState<Set<number>>(new Set());
  const [latched, setLatched] = useState<Set<number>>(new Set());
  const heldRef = useRef(new Set<number>());
  const optsRef = useRef(midiOpts);
  optsRef.current = midiOpts;
  const midiRef = useRef<MidiInput | null>(null);

  const connectMidi = useCallback((input: MidiInput) => {
    setMidiStatus('init');
    input
      .init()
      .then(() => {
        input.select(optsRef.current.device);
        setMidiStatus('ready');
        setMidiError(undefined);
      })
      .catch((e: unknown) => {
        const err = e instanceof Error ? e : new Error(String(e));
        // SecurityError / NotAllowedError — нет разрешения; InvalidStateError — нет драйвера MIDI в системе.
        setMidiStatus(err.name === 'SecurityError' || err.name === 'NotAllowedError' ? 'denied' : 'unavailable');
        setMidiError(err.message);
      });
  }, []);

  useEffect(() => {
    const input = new MidiInput({
      onNoteOn: (note, velocity) => {
        const wasEmpty = heldRef.current.size === 0;
        heldRef.current.add(note);
        setHeld(new Set(heldRef.current));
        if (optsRef.current.latch) {
          // Новый аккорд начинается, когда все клавиши были отпущены.
          setLatched((prev) => (wasEmpty ? new Set([note]) : new Set(prev).add(note)));
        }
        if (optsRef.current.sound) synth.playNote(note, velocity);
      },
      onNoteOff: (note) => {
        if (!heldRef.current.delete(note)) return;
        setHeld(new Set(heldRef.current));
      },
      onDevicesChanged: setDevices,
    });
    midiRef.current = input;
    if (!MidiInput.supported) {
      setMidiStatus('unsupported');
      return;
    }
    connectMidi(input);
    return () => input.dispose();
  }, [connectMidi]);

  useEffect(() => midiRef.current?.select(midiOpts.device), [midiOpts.device]);

  const midiActive = useMemo(() => new Set([...held, ...latched]), [held, latched]);

  // ---------- Определение аккорда ----------
  const boardNotes = useMemo(() => soundingNotes(board, tuning, view.realistic), [board, tuning, view.realistic]);
  const source: 'board' | 'midi' = midiActive.size > 0 ? 'midi' : 'board';
  const activeMidi = useMemo(
    () => (source === 'midi' ? [...midiActive].sort((a, b) => a - b) : boardNotes.map((n) => n.midi)),
    [source, midiActive, boardNotes],
  );
  const result = useMemo(() => detectChord(activeMidi), [activeMidi]);

  // История: добавляем аккорд, если он «устоялся» (не меняется ~0.8 с).
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
          tuning: view.tuning,
          board: source === 'board' ? board : undefined,
          midi: source === 'midi' ? activeMidi : undefined,
        };
        return [entry, ...h].slice(0, HISTORY_LIMIT);
      });
    }, 800);
    return () => clearTimeout(t);
  }, [result]);

  // ---------- Действия с грифом ----------
  const applyBoard = useCallback(
    (next: Board, play = sound.autoPlay) => {
      setBoard(next);
      if (play) playMidi(soundingNotes(next, tuning, view.realistic).map((n) => n.midi));
    },
    [setBoard, sound.autoPlay, playMidi, tuning, view.realistic],
  );

  const clearMidi = useCallback(() => {
    setLatched(new Set());
    heldRef.current.clear();
    setHeld(new Set());
  }, []);

  const onBoardEdit = (next: Board) => {
    // Правка грифа мышью возвращает определение к нотам грифа.
    if (midiActive.size) clearMidi();
    applyBoard(next);
  };

  const clearAll = useCallback(() => {
    synth.stopAll();
    clearMidi();
    setBoard(emptyBoard());
  }, [clearMidi, setBoard]);

  const playCurrent = useCallback(() => playMidi(activeMidi), [playMidi, activeMidi]);

  const saveShape = () => {
    const shape = source === 'midi' ? boardFromMidi(activeMidi, tuning) : board;
    const p = result.primary;
    const symbol = p?.symbol ?? (result.noteNames.join('-') || '—');
    setSaved((s) => [
      {
        id: uid(),
        name: symbol,
        symbol,
        nameRu: p ? p.nameRu : 'Неизвестный аккорд',
        tuning: view.tuning,
        board: shape,
        created: Date.now(),
      },
      ...s,
    ]);
  };

  const loadShape = (shape: Board, tuningId: TuningId) => {
    clearMidi();
    setView((v) => ({ ...v, tuning: tuningId }));
    setBoard(shape);
    playMidi(soundingNotes(shape, TUNINGS[tuningId].strings, view.realistic).map((n) => n.midi));
  };

  const pickHistory = (h: HistoryEntry) => {
    if (h.board) loadShape(h.board, h.tuning);
    else if (h.midi) loadShape(boardFromMidi(h.midi, TUNINGS[h.tuning].strings), h.tuning);
  };

  const onPianoKey = (m: number) => {
    setLatched((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else {
        next.add(m);
        synth.playNote(m, 0.8);
      }
      return next;
    });
  };

  // ---------- Горячие клавиши ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.code === 'Space') {
        e.preventDefault();
        playCurrent();
      } else if (e.key === 'Escape') synth.stopAll();
      else if (e.key === 'Delete' || e.key === 'Backspace') clearAll();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [playCurrent, clearAll]);

  useEffect(() => {
    document.documentElement.dataset.theme = view.theme;
  }, [view.theme]);

  const patchView = (p: Partial<ViewSettings>) => setView((v) => ({ ...v, ...p }));

  return (
    <div className={`app ${view.orientation}`}>
      <header className="topbar">
        <div className="brand">
          <span className="logo">🎸</span>
          <div>
            <h1>Гитарные аккорды</h1>
            <p>Поставьте точки на грифе — программа определит и сыграет аккорд</p>
          </div>
        </div>
        <div className="toolbar">
          <label className="field inline">
            <span>Строй</span>
            <select value={view.tuning} onChange={(e) => patchView({ tuning: e.target.value as TuningId })}>
              {Object.values(TUNINGS).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <div className="segmented" aria-label="Ориентация грифа">
            <button className={view.orientation === 'horizontal' ? 'on' : ''} onClick={() => patchView({ orientation: 'horizontal' })} title="Горизонтальный гриф">
              ⟷
            </button>
            <button className={view.orientation === 'vertical' ? 'on' : ''} onClick={() => patchView({ orientation: 'vertical' })} title="Вертикальный гриф">
              ↕
            </button>
          </div>
          <button className={`btn toggle ${view.showNotes ? 'on' : ''}`} onClick={() => patchView({ showNotes: !view.showNotes })}>
            Ноты на грифе
          </button>
          <button
            className={`btn toggle ${view.dotLabel === 'degree' ? 'on' : ''}`}
            onClick={() => patchView({ dotLabel: view.dotLabel === 'note' ? 'degree' : 'note' })}
            title="Подписи в точках: название ноты или ступень аккорда"
          >
            {view.dotLabel === 'note' ? 'Подписи: ноты' : 'Подписи: ступени'}
          </button>
          <button
            className={`btn toggle ${view.realistic ? 'on' : ''}`}
            onClick={() => patchView({ realistic: !view.realistic })}
            title="Как на настоящей гитаре: на каждой струне звучит только самый высокий зажатый лад"
          >
            Одна нота на струне
          </button>
          <button className="btn" onClick={() => patchView({ theme: view.theme === 'dark' ? 'light' : 'dark' })} title="Тема оформления">
            {view.theme === 'dark' ? '☀ Светлая' : '☾ Тёмная'}
          </button>
        </div>
      </header>

      <main className="workspace">
        <section className="panel board-panel">
          <div className="board-head">
            <span className="hint">
              Клик по клетке — поставить/снять точку · у порожка: O → X → пусто · правый клик — заглушить струну
            </span>
            <button className="btn danger" onClick={clearAll} disabled={isBoardEmpty(board) && midiActive.size === 0} title="Delete">
              ✕ Очистить все точки
            </button>
          </div>
          <div className="board-wrap">
            <Fretboard
              board={board}
              tuning={tuning}
              orientation={view.orientation}
              showNotes={view.showNotes}
              realistic={view.realistic}
              dotLabel={view.dotLabel}
              midiNotes={midiActive}
              degreeByPc={result.primary?.degreeByPc}
              rootPc={result.kind === 'chord' ? result.primary?.rootPc : undefined}
              onToggleFret={(s, f) => onBoardEdit(toggleFret(board, s, f))}
              onCycleNut={(s) => onBoardEdit(cycleNut(board, s))}
              onMuteString={(s) => onBoardEdit(setNut(board, s, board[s].muted ? 'none' : 'muted'))}
            />
          </div>
        </section>

        <div className="controls">
          <ChordDisplay
            result={result}
            soundingMidi={activeMidi}
            source={source}
            onPlay={playCurrent}
            onSave={saveShape}
            canSave={activeMidi.length > 0}
          />
          <SoundPanel
            settings={sound}
            onChange={(p) => setSound((s) => ({ ...s, ...p }))}
            onPlay={playCurrent}
            onStop={() => synth.stopAll()}
            canPlay={activeMidi.length > 0}
          />
          <MidiPanel
            status={midiStatus}
            error={midiError}
            devices={devices}
            selected={midiOpts.device}
            onSelect={(device) => setMidiOpts((o) => ({ ...o, device }))}
            active={midiActive}
            guitarRange={range}
            latch={midiOpts.latch}
            onLatch={(latch) => {
              setMidiOpts((o) => ({ ...o, latch }));
              if (!latch) setLatched(new Set());
            }}
            sound={midiOpts.sound}
            onSound={(v) => setMidiOpts((o) => ({ ...o, sound: v }))}
            onKey={onPianoKey}
            onClear={clearMidi}
            onRetry={() => midiRef.current && connectMidi(midiRef.current)}
            onToBoard={() => {
              const notes = activeMidi;
              clearMidi();
              applyBoard(boardFromMidi(notes, tuning));
            }}
          />
        </div>

        <aside className="side">
          <SavedPanel
            items={saved}
            onPick={(s) => loadShape(s.board, s.tuning)}
            onDelete={(id) => setSaved((list) => list.filter((s) => s.id !== id))}
            onRename={(id, name) => setSaved((list) => list.map((s) => (s.id === id ? { ...s, name } : s)))}
          />
          <HistoryPanel items={history} onPick={pickHistory} onClear={() => setHistory([])} />
        </aside>
      </main>
    </div>
  );
}
