import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { TIMBRE_NAMES, TIMBRE_PROGRAM, audio, type ChordNote } from './audio/engine';
import { ChordDisplay } from './components/ChordDisplay';
import { Fretboard, type CellFlash, type DotLabel } from './components/Fretboard';
import { KeyPanel, type ProgressionChord } from './components/KeyPanel';
import { LibraryPanel, type ChordRef } from './components/LibraryPanel';
import { MetronomePanel } from './components/MetronomePanel';
import { MidiPanel, type MidiStatus } from './components/MidiPanel';
import { ScalesPanel, type ScaleSettings } from './components/ScalesPanel';
import { SequencerPanel } from './components/SequencerPanel';
import { HistoryPanel, SavedPanel, type HistoryEntry, type SavedShape } from './components/SidePanels';
import { SoundPanel, type SoundSettings } from './components/SoundPanel';
import { TrainerPanel } from './components/TrainerPanel';
import { TunerPanel } from './components/TunerPanel';
import { AboutDialog, UpdateBanner, useUpdates } from './components/Updates';
import { renderDiagramPng } from './export/diagram';
import { copyText, pickFile, safeName, saveFile } from './export/download';
import { makeTab } from './export/tab';
import { ALL_DEVICES, MidiInput, type MidiDevice } from './midi/midiInput';
import { writeMidiFile, type MidiNoteEvent } from './midi/midiFile';
import { detectChord } from './music/chords';
import { computeFingering } from './music/fingering';
import {
  applyCapo,
  boardFromFrets,
  boardFromMidi,
  cycleNut,
  emptyBoard,
  instrumentRange,
  isBoardEmpty,
  setNut,
  soundingNotes,
  toggleFret,
  transposeBoard,
  type Board,
  type Frets,
} from './music/fretboard';
import { midiName, pcName } from './music/notes';
import { SCALES, scaleDegrees } from './music/scales';
import { MAX_CAPO, TUNINGS, TUNING_LIST, getTuning } from './music/tunings';
import { DEFAULT_RHYTHM, useSequencer, type RhythmSettings, type SeqItem } from './state/useSequencer';
import { useStored } from './state/useStored';

type TabId = 'sound' | 'midi' | 'library' | 'scales' | 'key' | 'sequence' | 'metronome' | 'tuner' | 'trainer';

const TABS: { id: TabId; label: string }[] = [
  { id: 'sound', label: '🔊 Звук' },
  { id: 'library', label: '📖 Справочник' },
  { id: 'scales', label: '🎼 Гаммы' },
  { id: 'key', label: '🗝 Тональность' },
  { id: 'sequence', label: '🎵 Последовательность' },
  { id: 'metronome', label: '⏱ Метроном' },
  { id: 'tuner', label: '🎤 Тюнер' },
  { id: 'trainer', label: '🎯 Тренажёр' },
  { id: 'midi', label: '🎹 MIDI' },
];

interface ViewSettings {
  theme: 'dark' | 'light';
  showNotes: boolean;
  dotLabel: DotLabel;
  tuning: string;
  customStrings: number[];
  capo: number;
  tab: TabId;
}

const DEFAULT_VIEW: ViewSettings = {
  theme: 'dark',
  showNotes: false,
  dotLabel: 'note',
  tuning: 'standard',
  customStrings: [...TUNINGS.standard.strings],
  capo: 0,
  tab: 'sound',
};

const DEFAULT_SOUND: SoundSettings = { volume: 0.8, reverb: 0.25, mode: 'strum', arpStepMs: 180, timbre: 'steel', autoPlay: true };
const DEFAULT_SCALE: ScaleSettings = { show: false, rootPc: 9, scaleId: 'pentMinor' };
const HISTORY_LIMIT = 40;
const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

/** Записи из версии 1.0 не знали о строе и каподастре — дополняем. */
function normalizeShape<T extends { tuning?: string; strings?: number[]; capo?: number }>(x: T): T & { strings: number[]; capo: number; tuning: string } {
  const tuning = x.tuning && TUNINGS[x.tuning] ? x.tuning : 'standard';
  return { ...x, tuning, strings: x.strings ?? TUNINGS[tuning].strings, capo: x.capo ?? 0 };
}

export default function App() {
  const [view, setView] = useStored<ViewSettings>('gc.view', DEFAULT_VIEW);
  const [sound, setSound] = useStored<SoundSettings>('gc.sound', DEFAULT_SOUND);
  const [rhythm, setRhythm] = useStored<RhythmSettings>('gc.rhythm', DEFAULT_RHYTHM);
  const [scaleSet, setScaleSet] = useStored<ScaleSettings>('gc.scale', DEFAULT_SCALE);
  const [board, setBoard] = useStored<Board>('gc.board', emptyBoard());
  const [history, setHistory] = useStored<HistoryEntry[]>('gc.history', []);
  const [saved, setSaved] = useStored<SavedShape[]>('gc.saved', []);
  const [sequence, setSequence] = useStored<SeqItem[]>('gc.sequence', []);
  const [midiOpts, setMidiOpts] = useStored('gc.midi', { latch: true, sound: true, device: ALL_DEVICES, output: '', muteInternal: false });
  const [toast, setToast] = useState<string | null>(null);
  const [flash, setFlash] = useState<CellFlash | null>(null);
  const [libRequest, setLibRequest] = useState<{ ref: ChordRef; nonce: number } | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const updates = useUpdates();

  const tuning = getTuning(view.tuning, view.customStrings);
  const strings = tuning.strings;
  const capo = Math.min(view.capo, MAX_CAPO);
  const range = useMemo(() => instrumentRange(strings.map((s) => s + capo)), [strings, capo]);
  const patchView = (p: Partial<ViewSettings>) => setView((v) => ({ ...v, ...p }));

  // Совместимость с сохранёнными настройками версии 1.0.
  useEffect(() => {
    if (!(sound.timbre in TIMBRE_NAMES)) setSound((s) => ({ ...s, timbre: 'steel' }));
    if (!TABS.some((t) => t.id === view.tab)) patchView({ tab: 'sound' });
    if (!TUNINGS[view.tuning]) patchView({ tuning: 'standard' });
    setSaved((list) => list.map(normalizeShape));
    setHistory((list) => list.map(normalizeShape));
  }, []);

  // Число струн доски = число струн инструмента.
  useEffect(() => {
    if (board.length !== strings.length) setBoard(emptyBoard(strings.length));
  }, [board.length, strings.length, setBoard]);

  const showToast = useCallback((text: string) => {
    setToast(text);
    window.setTimeout(() => setToast((t) => (t === text ? null : t)), 2600);
  }, []);

  // ---------- Звук ----------
  useEffect(() => audio.setVolume(sound.volume), [sound.volume]);
  useEffect(() => audio.setReverb(sound.reverb), [sound.reverb]);
  useEffect(() => audio.setTimbre(sound.timbre), [sound.timbre]);
  useEffect(() => audio.setInstrument(tuning.instrument), [tuning.instrument]);

  const notesOf = useCallback(
    (b: Board, s = strings, c = capo): ChordNote[] => soundingNotes(b, s, c).map((n) => ({ midi: n.midi, string: n.string })),
    [strings, capo],
  );
  const playNotes = useCallback((notes: ChordNote[]) => audio.playChord(notes, sound.mode, sound.arpStepMs), [sound.mode, sound.arpStepMs]);

  // ---------- MIDI ----------
  const [midiStatus, setMidiStatus] = useState<MidiStatus>('init');
  const [midiError, setMidiError] = useState<string>();
  const [devices, setDevices] = useState<MidiDevice[]>([]);
  const [outputs, setOutputs] = useState<MidiDevice[]>([]);
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
        input.selectOutput(optsRef.current.output || null);
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
        if (optsRef.current.latch) setLatched((prev) => (wasEmpty ? new Set([note]) : new Set(prev).add(note)));
        if (optsRef.current.sound) audio.playNote(note, velocity);
      },
      onNoteOff: (note) => {
        if (!heldRef.current.delete(note)) return;
        setHeld(new Set(heldRef.current));
      },
      onDevicesChanged: (ins, outs) => {
        setDevices(ins);
        setOutputs(outs);
      },
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
  useEffect(() => {
    midiRef.current?.selectOutput(midiOpts.output || null);
    audio.onNoteOut = midiOpts.output ? (m, v, d, dur) => midiRef.current?.sendNote(m, v, d, dur) : null;
    audio.muted = Boolean(midiOpts.output && midiOpts.muteInternal);
  }, [midiOpts.output, midiOpts.muteInternal]);

  const midiActive = useMemo(() => new Set([...held, ...latched]), [held, latched]);

  // ---------- Определение аккорда ----------
  const boardNotes = useMemo(() => soundingNotes(board, strings, capo), [board, strings, capo]);
  const source: 'board' | 'midi' = midiActive.size > 0 ? 'midi' : 'board';
  const activeMidi = useMemo(
    () => (source === 'midi' ? [...midiActive].sort((a, b) => a - b) : boardNotes.map((n) => n.midi)),
    [source, midiActive, boardNotes],
  );
  const result = useMemo(() => detectChord(activeMidi), [activeMidi]);
  const shapeSymbol = useMemo(
    () => (capo > 0 && source === 'board' ? detectChord(activeMidi.map((m) => m - capo)).primary?.symbol : undefined),
    [capo, source, activeMidi],
  );
  const fingering = useMemo(() => computeFingering(board, capo), [board, capo]);
  const chordRef: ChordRef | undefined =
    result.kind === 'chord' && result.primary
      ? {
          rootPc: result.primary.rootPc,
          templateId: result.primary.template.id,
          bassPc: result.primary.bassPc !== result.primary.rootPc ? result.primary.bassPc : undefined,
        }
      : undefined;

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

  // ---------- Действия с грифом ----------
  const clearMidi = useCallback(() => {
    setLatched(new Set());
    heldRef.current.clear();
    setHeld(new Set());
  }, []);

  const applyBoard = useCallback(
    (next: Board, play = sound.autoPlay) => {
      setBoard(next);
      if (play) playNotes(notesOf(next));
    },
    [setBoard, sound.autoPlay, playNotes, notesOf],
  );

  const onBoardEdit = (next: Board) => {
    if (midiActive.size) clearMidi();
    applyBoard(next);
  };

  // Тренажёр может перехватывать клики по грифу.
  const cellHandlerRef = useRef<((s: number, f: number) => boolean) | null>(null);
  const registerCellHandler = useCallback((fn: ((s: number, f: number) => boolean) | null) => {
    cellHandlerRef.current = fn;
    if (!fn) setFlash(null);
  }, []);

  const loadFrets = useCallback(
    (frets: Frets) => {
      clearMidi();
      applyBoard(boardFromFrets(frets, capo), true);
    },
    [applyBoard, capo, clearMidi],
  );

  const clearAll = useCallback(() => {
    audio.stopAll();
    clearMidi();
    setBoard(emptyBoard(strings.length));
  }, [clearMidi, setBoard, strings.length]);

  const transpose = useCallback(
    (k: number) => {
      if (source === 'midi') {
        setLatched((prev) => new Set([...prev].map((m) => m + k)));
        return;
      }
      if (isBoardEmpty(board)) return;
      const next = transposeBoard(board, k, capo);
      if (!next) {
        showToast(k > 0 ? 'Выше нельзя: аппликатура выйдет за 15-й лад' : 'Ниже нельзя: аппликатура упирается в порожек');
        return;
      }
      applyBoard(next);
    },
    [source, board, capo, applyBoard, showToast],
  );

  const setCapo = (c: number) => {
    patchView({ capo: c });
    setBoard((b) => applyCapo(b, c));
  };

  const setTuning = (id: string) => {
    const next = getTuning(id, view.customStrings);
    patchView({ tuning: id, capo: next.instrument === 'guitar' ? capo : 0 });
  };

  const playCurrent = useCallback(() => {
    if (source === 'board') playNotes(notesOf(board));
    else playNotes(activeMidi.map((midi) => ({ midi })));
  }, [source, board, activeMidi, playNotes, notesOf]);

  const currentNotes = (): ChordNote[] => (source === 'board' ? notesOf(board) : activeMidi.map((midi) => ({ midi })));
  const currentBoard = (): Board => (source === 'midi' ? boardFromMidi(activeMidi, strings, capo) : board);
  const currentSymbol = () => result.primary?.symbol ?? (result.noteNames.join('-') || 'аккорд');

  const saveShape = () => {
    const p = result.primary;
    const symbol = currentSymbol();
    setSaved((s) => [
      {
        id: uid(),
        name: symbol,
        symbol,
        nameRu: p ? p.nameRu : 'Неизвестный аккорд',
        tuning: view.tuning,
        strings,
        capo,
        board: currentBoard(),
        created: Date.now(),
      },
      ...s,
    ]);
    showToast(`«${symbol}» добавлен в избранное`);
  };

  const loadShape = (shape: Board, tuningId: string, shapeStrings: number[], shapeCapo: number) => {
    clearMidi();
    if (tuningId === 'custom') patchView({ tuning: tuningId, customStrings: shapeStrings, capo: shapeCapo });
    else patchView({ tuning: tuningId, capo: shapeCapo });
    setBoard(shape);
    playNotes(soundingNotes(shape, shapeStrings, shapeCapo).map((n) => ({ midi: n.midi, string: n.string })));
  };

  const pickHistory = (h: HistoryEntry) => {
    const e = normalizeShape(h);
    if (e.board) loadShape(e.board, e.tuning, e.strings, e.capo);
    else if (e.midi) loadShape(boardFromMidi(e.midi, e.strings, e.capo), e.tuning, e.strings, e.capo);
  };

  const onPianoKey = (m: number) => {
    setLatched((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else {
        next.add(m);
        audio.playNote(m, 0.8);
      }
      return next;
    });
  };

  // ---------- Последовательность ----------
  const seq = useSequencer(sequence, rhythm, (item) => {
    if (item.strings.length === strings.length) setBoard(item.board);
  });
  const makeItem = (symbol: string, b: Board, beats = 4): SeqItem => ({ id: uid(), symbol, board: b, strings, capo, beats });
  const addToSequence = () => {
    setSequence((list) => [...list, makeItem(currentSymbol(), currentBoard())]);
    showToast(`«${currentSymbol()}» добавлен в последовательность`);
  };
  const progressionItems = (chords: ProgressionChord[]) => chords.map((c) => makeItem(c.symbol, boardFromFrets(c.frets, capo)));

  // ---------- Экспорт ----------
  const program = tuning.instrument === 'bass' ? TIMBRE_PROGRAM.bass : TIMBRE_PROGRAM[sound.timbre];
  const exportChord = async (kind: 'png' | 'midi' | 'tab') => {
    const symbol = currentSymbol();
    const b = currentBoard();
    if (kind === 'png') {
      const blob = await renderDiagramPng({
        board: b,
        capo,
        title: symbol,
        subtitle: result.primary?.nameRu,
        fingering: computeFingering(b, capo),
        stringLabels: strings.map((s) => pcName(s)),
      });
      saveFile(blob, `${safeName(symbol)}.png`, 'image/png');
    } else if (kind === 'midi') {
      const events: MidiNoteEvent[] = currentNotes()
        .sort((a, b2) => a.midi - b2.midi)
        .map((n, i) => ({ midi: n.midi, start: i * 0.03, duration: 4 - i * 0.03, velocity: 0.8 }));
      saveFile(writeMidiFile(events, rhythm.bpm, program, symbol), `${safeName(symbol)}.mid`, 'audio/midi');
    } else {
      const text = makeTab([{ symbol, board: b }], strings, capo, `${symbol}${result.primary ? ' — ' + result.primary.nameRu : ''}`);
      const copied = await copyText(text);
      saveFile(text, `${safeName(symbol)}.txt`, 'text/plain;charset=utf-8');
      if (copied) showToast('Табулатура скопирована в буфер обмена');
    }
  };

  const exportSequence = async (kind: 'midi' | 'tab') => {
    if (!sequence.length) return;
    if (kind === 'midi') {
      const events: MidiNoteEvent[] = [];
      let t = 0;
      for (const it of sequence) {
        soundingNotes(it.board, it.strings, it.capo).forEach((n, i) =>
          events.push({ midi: n.midi, start: t + i * 0.03, duration: it.beats - i * 0.03, velocity: 0.8 }),
        );
        t += it.beats;
      }
      saveFile(writeMidiFile(events, rhythm.bpm, program, 'Последовательность'), 'progression.mid', 'audio/midi');
    } else {
      const text = makeTab(sequence.map((it) => ({ symbol: it.symbol, board: it.board })), sequence[0].strings, sequence[0].capo);
      const copied = await copyText(text);
      saveFile(text, 'progression.txt', 'text/plain;charset=utf-8');
      if (copied) showToast('Табулатура скопирована в буфер обмена');
    }
  };

  const exportFavorites = () => {
    saveFile(JSON.stringify({ app: 'GuitarChords', version: 1, saved }, null, 2), 'favorites.json', 'application/json');
  };
  const importFavorites = async () => {
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
      showToast(`Загружено аппликатур: ${valid.length}`);
    } catch {
      showToast('Не удалось прочитать файл избранного');
    }
  };

  // ---------- Горячие клавиши ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.code === 'Space') {
        e.preventDefault();
        playCurrent();
      } else if (e.key === 'Escape') {
        audio.stopAll();
        seq.stop();
      } else if (e.key === 'Delete' || e.key === 'Backspace') clearAll();
      else if (e.key === 'ArrowRight') transpose(1);
      else if (e.key === 'ArrowLeft') transpose(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [playCurrent, clearAll, transpose, seq]);

  useEffect(() => {
    document.documentElement.dataset.theme = view.theme;
  }, [view.theme]);

  const scale = SCALES.find((s) => s.id === scaleSet.scaleId) ?? SCALES[0];
  const scaleOverlay = scaleSet.show ? { rootPc: scaleSet.rootPc, degrees: scaleDegrees(scaleSet.rootPc, scale) } : null;

  const playScale = (steps: number[], rootPc: number) => {
    const low = Math.min(...strings) + capo;
    let start = low;
    while (start % 12 !== rootPc) start++;
    const notes = [...steps.map((s) => start + s), start + 12];
    audio.stopAll(0.03);
    notes.forEach((m, i) => audio.playNote(m, 0.8, audio.now + i * 0.28, 'scale', 0.6));
  };

  return (
    <div className="app">
      <UpdateBanner status={updates.status} />
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
            <select value={view.tuning} onChange={(e) => setTuning(e.target.value)}>
              {[...new Set(TUNING_LIST.map((t) => t.group))].map((g) => (
                <optgroup key={g} label={g}>
                  {TUNING_LIST.filter((t) => t.group === g).map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="field inline" title="Каподастр зажимает все струны на выбранном ладу">
            <span>Каподастр</span>
            <select value={capo} onChange={(e) => setCapo(Number(e.target.value))}>
              <option value={0}>нет</option>
              {Array.from({ length: MAX_CAPO }, (_, i) => i + 1).map((c) => (
                <option key={c} value={c}>
                  {c} лад
                </option>
              ))}
            </select>
          </label>
          <div className="transpose" title="Сдвинуть аккорд на полтона (стрелки ← →)">
            <span>Тон</span>
            <button className="btn small" onClick={() => transpose(-1)}>
              −½
            </button>
            <button className="btn small" onClick={() => transpose(1)}>
              +½
            </button>
          </div>
          <button className={`btn toggle ${view.showNotes ? 'on' : ''}`} onClick={() => patchView({ showNotes: !view.showNotes })}>
            Ноты на грифе
          </button>
          <label className="field inline" title="Что писать внутри точек на грифе">
            <span>В точках</span>
            <select value={view.dotLabel} onChange={(e) => patchView({ dotLabel: e.target.value as DotLabel })}>
              <option value="note">названия нот</option>
              <option value="degree">ступени аккорда</option>
              <option value="finger">номера пальцев</option>
            </select>
          </label>
          <button className="btn" onClick={() => patchView({ theme: view.theme === 'dark' ? 'light' : 'dark' })} title="Тема оформления">
            {view.theme === 'dark' ? '☀' : '☾'}
          </button>
          <button className="btn" onClick={() => setAboutOpen(true)} title="О программе и обновления">
            ℹ
          </button>
        </div>
      </header>

      {view.tuning === 'custom' && (
        <div className="custom-tuning">
          <span>Свой строй (от басовой струны):</span>
          {view.customStrings.map((m, i) => (
            <select
              key={i}
              value={m}
              onChange={(e) => patchView({ customStrings: view.customStrings.map((x, j) => (j === i ? Number(e.target.value) : x)) })}
            >
              {Array.from({ length: 49 }, (_, k) => 28 + k).map((n) => (
                <option key={n} value={n}>
                  {midiName(n)}
                </option>
              ))}
            </select>
          ))}
          <button className="btn small" onClick={() => patchView({ customStrings: [...TUNINGS.standard.strings] })}>
            Сбросить
          </button>
        </div>
      )}

      <main className="workspace">
        <section className="panel board-panel">
          <div className="board-head">
            <span className="hint">
              Клик по клетке — поставить/убрать точку · у порожка: O (открытая) → X (не играет) → пусто · правый клик — заглушить
              {view.tab === 'trainer' && cellHandlerRef.current ? ' · сейчас клики проверяет тренажёр' : ''}
            </span>
            <div className="row">
              {scaleSet.show && (
                <button className="btn small toggle on" onClick={() => setScaleSet((s) => ({ ...s, show: false }))} title="Скрыть гамму">
                  Гамма: {pcName(scaleSet.rootPc)} {scale.name.split(' (')[0].toLowerCase()} ✕
                </button>
              )}
              <button className="btn danger" onClick={clearAll} disabled={isBoardEmpty(board) && midiActive.size === 0} title="Delete">
                ✕ Очистить все точки
              </button>
            </div>
          </div>
          <Fretboard
            board={board}
            tuning={strings}
            capo={capo}
            showNotes={view.showNotes}
            dotLabel={view.dotLabel}
            midiNotes={midiActive}
            degreeByPc={result.primary?.degreeByPc}
            rootPc={result.kind === 'chord' ? result.primary?.rootPc : undefined}
            fingering={fingering}
            scale={scaleOverlay}
            flash={flash}
            onToggleFret={(s, f) => {
              if (cellHandlerRef.current?.(s, f)) return;
              onBoardEdit(toggleFret(board, s, f));
            }}
            onCycleNut={(s) => {
              if (cellHandlerRef.current?.(s, capo)) return;
              onBoardEdit(cycleNut(board, s));
            }}
            onMuteString={(s) => onBoardEdit(setNut(board, s, board[s].muted ? 'none' : 'muted'))}
          />
        </section>

        <ChordDisplay
          result={result}
          soundingMidi={activeMidi}
          source={source}
          capo={capo}
          shapeSymbol={shapeSymbol}
          warnings={source === 'board' ? fingering.warnings : []}
          onPlay={playCurrent}
          onSave={saveShape}
          onAddToSequence={addToSequence}
          onShowVoicings={
            chordRef
              ? () => {
                  setLibRequest({ ref: chordRef, nonce: Date.now() });
                  patchView({ tab: 'library' });
                }
              : undefined
          }
          onExport={(k) => void exportChord(k)}
        />

        <section className="panel tools">
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t.id} className={view.tab === t.id ? 'on' : ''} onClick={() => patchView({ tab: t.id })}>
                {t.label}
                {t.id === 'sequence' && seq.playing ? ' ▶' : ''}
              </button>
            ))}
          </nav>
          {view.tab === 'sound' && (
            <SoundPanel
              settings={sound}
              instrument={tuning.instrument}
              onChange={(p) => setSound((s) => ({ ...s, ...p }))}
              onPlay={playCurrent}
              onStrum={(dir) => {
                audio.stopAll(0.02);
                audio.strum(currentNotes(), dir);
              }}
              onArpeggio={() => {
                audio.stopAll(0.02);
                audio.arpeggio(currentNotes(), sound.arpStepMs);
              }}
              onStop={() => audio.stopAll()}
              canPlay={activeMidi.length > 0}
            />
          )}
          {view.tab === 'library' && (
            <LibraryPanel tuning={strings} capo={capo} current={chordRef} request={libRequest} onPick={(frets) => loadFrets(frets)} />
          )}
          {view.tab === 'scales' && (
            <ScalesPanel settings={scaleSet} onChange={(p) => setScaleSet((s) => ({ ...s, ...p }))} onPlay={playScale} />
          )}
          {view.tab === 'key' && (
            <KeyPanel
              tuning={strings}
              capo={capo}
              onPick={(frets) => loadFrets(frets)}
              onPlayProgression={(chords) => seq.play(progressionItems(chords))}
              onToSequence={(chords) => {
                setSequence(progressionItems(chords));
                patchView({ tab: 'sequence' });
              }}
            />
          )}
          {view.tab === 'sequence' && (
            <SequencerPanel
              items={sequence}
              rhythm={rhythm}
              onRhythm={(p) => setRhythm((r) => ({ ...r, ...p }))}
              playing={seq.playing}
              current={seq.current}
              canAdd={activeMidi.length > 0}
              onAdd={addToSequence}
              onChange={setSequence}
              onLoad={(it) => loadShape(it.board, view.tuning, it.strings, it.capo)}
              onPlay={() => seq.play()}
              onStop={seq.stop}
              onExportMidi={() => void exportSequence('midi')}
              onExportTab={() => void exportSequence('tab')}
            />
          )}
          {view.tab === 'metronome' && <MetronomePanel rhythm={rhythm} onRhythm={(p) => setRhythm((r) => ({ ...r, ...p }))} />}
          {view.tab === 'tuner' && (
            <TunerPanel
              tuning={strings}
              capo={capo}
              onChordToBoard={(midis) => {
                clearMidi();
                applyBoard(boardFromMidi(midis, strings, capo), true);
              }}
            />
          )}
          {view.tab === 'trainer' && (
            <TrainerPanel
              tuning={strings}
              capo={capo}
              soundingMidis={boardNotes.map((n) => n.midi)}
              registerCellHandler={registerCellHandler}
              setFlash={setFlash}
              loadFrets={(frets) => loadFrets(frets)}
              clearBoard={() => setBoard(emptyBoard(strings.length))}
            />
          )}
          {view.tab === 'midi' && (
            <MidiPanel
              status={midiStatus}
              error={midiError}
              devices={devices}
              outputs={outputs}
              selected={midiOpts.device}
              onSelect={(device) => setMidiOpts((o) => ({ ...o, device }))}
              output={midiOpts.output}
              onOutput={(output) => setMidiOpts((o) => ({ ...o, output }))}
              muteInternal={midiOpts.muteInternal}
              onMuteInternal={(muteInternal) => setMidiOpts((o) => ({ ...o, muteInternal }))}
              active={midiActive}
              range={range}
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
                applyBoard(boardFromMidi(notes, strings, capo));
              }}
            />
          )}
        </section>

        <aside className="side">
          <SavedPanel
            items={saved}
            onPick={(s) => {
              const n = normalizeShape(s);
              loadShape(n.board, n.tuning, n.strings, n.capo);
            }}
            onDelete={(id) => setSaved((list) => list.filter((s) => s.id !== id))}
            onRename={(id, name) => setSaved((list) => list.map((s) => (s.id === id ? { ...s, name } : s)))}
            onExport={exportFavorites}
            onImport={() => void importFavorites()}
          />
          <HistoryPanel items={history} onPick={pickHistory} onClear={() => setHistory([])} />
        </aside>
      </main>

      {toast && <div className="toast">{toast}</div>}
      {aboutOpen && <AboutDialog info={updates.info} status={updates.status} onClose={() => setAboutOpen(false)} />}
    </div>
  );
}
