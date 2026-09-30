// Экспорт аккорда и последовательности: PNG-диаграмма, MIDI-файл, текстовая табулатура.

import { TIMBRE_PROGRAM } from '../core/audio/engine';
import { renderDiagramPng } from '../core/export/diagram';
import { copyText, safeName, saveFile } from '../core/export/download';
import { makeTab } from '../core/export/tab';
import { writeMidiFile, type MidiNoteEvent } from '../core/midi/midiFile';
import { computeFingering } from '../core/music/fingering';
import { soundingNotes } from '../core/music/fretboard';
import { pcName } from '../core/music/notes';
import type { SeqItem } from '../store/model';
import { store } from '../store';

const program = () => {
  const s = store.getState();
  return s.guitar().tuning.instrument === 'bass' ? TIMBRE_PROGRAM.bass : TIMBRE_PROGRAM[s.settings.sound.timbre];
};

async function saveTab(text: string, name: string) {
  const copied = await copyText(text);
  saveFile(text, name, 'text/plain;charset=utf-8');
  if (copied) store.getState().toast('Табулатура скопирована в буфер обмена');
}

export async function exportChord(kind: 'png' | 'midi' | 'tab') {
  const s = store.getState();
  const g = s.guitar();
  const symbol = s.currentSymbol();
  const b = s.currentBoard();
  if (kind === 'png') {
    const blob = await renderDiagramPng({
      board: b,
      capo: g.capo,
      title: symbol,
      subtitle: g.result.primary?.nameRu,
      fingering: computeFingering(b, g.capo),
      stringLabels: g.strings.map((x) => pcName(x)),
    });
    saveFile(blob, `${safeName(symbol)}.png`, 'image/png');
  } else if (kind === 'midi') {
    const events: MidiNoteEvent[] = s
      .currentNotes()
      .sort((a, c) => a.midi - c.midi)
      .map((n, i) => ({ midi: n.midi, start: i * 0.03, duration: 4 - i * 0.03, velocity: 0.8 }));
    saveFile(writeMidiFile(events, s.settings.rhythm.bpm, program(), symbol), `${safeName(symbol)}.mid`, 'audio/midi');
  } else {
    const title = `${symbol}${g.result.primary ? ' — ' + g.result.primary.nameRu : ''}`;
    await saveTab(makeTab([{ symbol, board: b }], g.strings, g.capo, title), `${safeName(symbol)}.txt`);
  }
}

export async function exportSequence(sequence: SeqItem[], kind: 'midi' | 'tab') {
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
    saveFile(writeMidiFile(events, store.getState().settings.rhythm.bpm, program(), 'Последовательность'), 'progression.mid', 'audio/midi');
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
}
