// Экспорт аккорда и последовательности: PNG-диаграмма, MIDI-файл, текстовая табулатура.

import { TIMBRE_PROGRAM } from '../core/audio/engine';
import { renderDiagramPng } from '../core/export/diagram';
import { copyText, safeName, saveFile } from '../core/export/download';
import { makeTab } from '../core/export/tab';
import { writeMidiFile, type MidiNoteEvent } from '../core/midi/midiFile';
import { computeFingering } from '../core/music/fingering';
import { soundingNotes } from '../core/music/fretboard';
import { pcName } from '../core/music/notes';
import type { SeqItem } from '../features/sequencer/useSequencer';
import type { Settings } from './settings';
import type { Guitar } from './useGuitar';

export function useExports(settings: Settings, guitar: Guitar, toast: (text: string) => void) {
  const { strings, capo, result } = guitar;
  const program = guitar.tuning.instrument === 'bass' ? TIMBRE_PROGRAM.bass : TIMBRE_PROGRAM[settings.sound.timbre];
  const bpm = settings.rhythm.bpm;

  const saveTab = async (text: string, name: string) => {
    const copied = await copyText(text);
    saveFile(text, name, 'text/plain;charset=utf-8');
    if (copied) toast('Табулатура скопирована в буфер обмена');
  };

  const exportChord = async (kind: 'png' | 'midi' | 'tab') => {
    const symbol = guitar.currentSymbol();
    const b = guitar.currentBoard();
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
      const events: MidiNoteEvent[] = guitar
        .currentNotes()
        .sort((a, c) => a.midi - c.midi)
        .map((n, i) => ({ midi: n.midi, start: i * 0.03, duration: 4 - i * 0.03, velocity: 0.8 }));
      saveFile(writeMidiFile(events, bpm, program, symbol), `${safeName(symbol)}.mid`, 'audio/midi');
    } else {
      const title = `${symbol}${result.primary ? ' — ' + result.primary.nameRu : ''}`;
      await saveTab(makeTab([{ symbol, board: b }], strings, capo, title), `${safeName(symbol)}.txt`);
    }
  };

  const exportSequence = async (sequence: SeqItem[], kind: 'midi' | 'tab') => {
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
      saveFile(writeMidiFile(events, bpm, program, 'Последовательность'), 'progression.mid', 'audio/midi');
    } else {
      await saveTab(
        makeTab(
          sequence.map((it) => ({ symbol: it.symbol, board: it.board })),
          sequence[0].strings,
          sequence[0].capo,
        ),
        'progression.txt',
      );
    }
  };

  return {
    exportChord: (k: 'png' | 'midi' | 'tab') => void exportChord(k),
    exportSequence: (seq: SeqItem[], k: 'midi' | 'tab') => void exportSequence(seq, k),
  };
}
