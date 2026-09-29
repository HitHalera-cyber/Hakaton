// Инструмент и гриф: строй, каподастр, точки, звучащие ноты, определение аккорда и действия с грифом.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { audio, type ChordNote } from '../core/audio/engine';
import { CHORD_TEMPLATES, detectChord } from '../core/music/chords';
import { computeFingering } from '../core/music/fingering';
import {
  applyCapo,
  boardFromFrets,
  boardFromMidi,
  emptyBoard,
  instrumentRange,
  isBoardEmpty,
  soundingNotes,
  transposeBoard,
  type Board,
  type Frets,
} from '../core/music/fretboard';
import { MAX_CAPO, getTuning } from '../core/music/tunings';
import { generateVoicings } from '../core/music/voicings';
import type { CellFlash } from '../features/fretboard/Fretboard';
import type { ChordRef } from '../features/library/LibraryPanel';
import type { Settings } from './settings';
import type { MidiIO } from './useMidiIO';
import { useStored } from './useStored';

export function useGuitar(settings: Settings, midi: MidiIO, toast: (text: string) => void) {
  const { view, patchView, sound } = settings;
  const { clear: clearMidi, shift: shiftMidi, active: midiActive } = midi;
  const [board, setBoard] = useStored<Board>('gc.board', emptyBoard());
  const tuning = getTuning(view.tuning, view.customStrings);
  const strings = tuning.strings;
  const capo = Math.min(view.capo, MAX_CAPO);
  const range = useMemo(() => instrumentRange(strings.map((s) => s + capo)), [strings, capo]);

  // Число струн доски = число струн инструмента.
  useEffect(() => {
    if (board.length !== strings.length) setBoard(emptyBoard(strings.length));
  }, [board.length, strings.length, setBoard]);

  // Звук следует за настройками.
  useEffect(() => audio.setVolume(sound.volume), [sound.volume]);
  useEffect(() => audio.setReverb(sound.reverb), [sound.reverb]);
  useEffect(() => audio.setTimbre(sound.timbre), [sound.timbre]);
  useEffect(() => audio.setInstrument(tuning.instrument), [tuning.instrument]);

  const notesOf = useCallback(
    (b: Board, s = strings, c = capo): ChordNote[] => soundingNotes(b, s, c).map((n) => ({ midi: n.midi, string: n.string })),
    [strings, capo],
  );
  const playNotes = useCallback((notes: ChordNote[]) => audio.playChord(notes, sound.mode, sound.arpStepMs), [sound.mode, sound.arpStepMs]);

  // ---------- Что звучит и какой это аккорд ----------
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

  // ---------- Действия ----------
  const apply = useCallback(
    (next: Board, play = sound.autoPlay) => {
      setBoard(next);
      if (play) playNotes(notesOf(next));
    },
    [setBoard, sound.autoPlay, playNotes, notesOf],
  );

  /** Правка грифа мышью: определение возвращается к нотам грифа. */
  const edit = (next: Board) => {
    if (midiActive.size) clearMidi();
    apply(next);
  };

  const loadFrets = useCallback(
    (frets: Frets, play = true) => {
      clearMidi();
      apply(boardFromFrets(frets, capo), play);
    },
    [apply, capo, clearMidi],
  );

  const voicingFor = useCallback(
    (rootPc: number, templateId: string, bassPc?: number): Frets | null => {
      const t = CHORD_TEMPLATES.find((x) => x.id === templateId);
      if (!t) return null;
      return (
        generateVoicings(rootPc, t, strings, { capo, bassPc, limit: 1 })[0]?.frets ??
        generateVoicings(rootPc, t, strings, { capo, limit: 1 })[0]?.frets ??
        null
      );
    },
    [strings, capo],
  );

  /** Поставить аккорд на гриф удобной аппликатурой (без звука: играет песня или гитарист). */
  const showChord = useCallback(
    (rootPc: number, templateId: string, bassPc?: number) => {
      const frets = voicingFor(rootPc, templateId, bassPc);
      if (frets) loadFrets(frets, false);
    },
    [voicingFor, loadFrets],
  );

  const clear = useCallback(() => {
    audio.stopAll();
    clearMidi();
    setBoard(emptyBoard(strings.length));
  }, [clearMidi, setBoard, strings.length]);

  const transpose = useCallback(
    (k: number) => {
      if (source === 'midi') return shiftMidi(k);
      if (isBoardEmpty(board)) return;
      const next = transposeBoard(board, k, capo);
      if (!next) return toast(k > 0 ? 'Выше нельзя: аппликатура выйдет за 15-й лад' : 'Ниже нельзя: аппликатура упирается в порожек');
      apply(next);
    },
    [source, board, capo, apply, toast, shiftMidi],
  );

  const setCapo = useCallback(
    (c: number) => {
      patchView({ capo: c });
      setBoard((b) => applyCapo(b, c));
    },
    [patchView, setBoard],
  );

  const setTuning = (id: string) => {
    const next = getTuning(id, view.customStrings);
    patchView({ tuning: id, capo: next.instrument === 'guitar' ? capo : 0 });
  };

  const currentNotes = useCallback(
    (): ChordNote[] => (source === 'board' ? notesOf(board) : activeMidi.map((m) => ({ midi: m }))),
    [source, board, activeMidi, notesOf],
  );
  const play = useCallback(() => playNotes(currentNotes()), [playNotes, currentNotes]);
  const currentBoard = (): Board => (source === 'midi' ? boardFromMidi(activeMidi, strings, capo) : board);
  const currentSymbol = () => result.primary?.symbol ?? (result.noteNames.join('-') || 'аккорд');

  /** Загрузить сохранённую аппликатуру вместе с её строем и каподастром. */
  const loadShape = (shape: Board, tuningId: string, shapeStrings: number[], shapeCapo: number) => {
    clearMidi();
    if (tuningId === 'custom') patchView({ tuning: tuningId, customStrings: shapeStrings, capo: shapeCapo });
    else patchView({ tuning: tuningId, capo: shapeCapo });
    setBoard(shape);
    playNotes(soundingNotes(shape, shapeStrings, shapeCapo).map((n) => ({ midi: n.midi, string: n.string })));
  };

  // ---------- Тренажёр может перехватывать клики по грифу ----------
  const cellHandler = useRef<((s: number, f: number) => boolean) | null>(null);
  const [flash, setFlash] = useState<CellFlash | null>(null);
  const registerCellHandler = useCallback((fn: ((s: number, f: number) => boolean) | null) => {
    cellHandler.current = fn;
    if (!fn) setFlash(null);
  }, []);

  return {
    tuning,
    strings,
    capo,
    range,
    board,
    setBoard,
    boardNotes,
    source,
    activeMidi,
    result,
    shapeSymbol,
    fingering,
    chordRef,
    apply,
    edit,
    loadFrets,
    voicingFor,
    showChord,
    clear,
    transpose,
    setCapo,
    setTuning,
    play,
    playNotes,
    notesOf,
    currentNotes,
    currentBoard,
    currentSymbol,
    loadShape,
    cellHandler,
    registerCellHandler,
    flash,
    setFlash,
  };
}

export type Guitar = ReturnType<typeof useGuitar>;
