// Связи между частями приложения. Здесь (и только здесь) одно событие приводит к действиям в нескольких местах:
// услышанный аккорд — на гриф, на круг и в статистику; аккорд с грифа — в историю и на круг и т. д.

import { audio } from '../core/audio/engine';
import { boardFromMidi, emptyBoard } from '../core/music/fretboard';
import { store } from '../store';
import { bus } from './bus';
import { chordListener } from './chordListener';
import { metronome } from './metronome';
import { mic } from './mic';
import { midiService } from './midi';
import { sequencer } from './sequencer';

let started = false;

export function startServices() {
  if (started) return;
  started = true;
  const s0 = store.getState();

  // ---------- Звук следует за настройками ----------
  const syncAudio = () => {
    const s = store.getState();
    audio.setVolume(s.settings.sound.volume);
    audio.setReverb(s.settings.sound.reverb);
    audio.setTimbre(s.settings.sound.timbre);
    audio.setInstrument(s.guitar().tuning.instrument);
  };
  syncAudio();
  mic.setGain(store.getState().settings.listen.gain);
  mic.setAutoGain(store.getState().settings.listen.autoGain);
  void mic.setDevice(store.getState().settings.listen.deviceId);
  store.subscribe((s, prev) => {
    if (s.settings.sound !== prev.settings.sound || s.settings.view.tuning !== prev.settings.view.tuning) syncAudio();
    const l = s.settings.listen;
    if (l.gain !== prev.settings.listen.gain) mic.setGain(l.gain);
    if (l.autoGain !== prev.settings.listen.autoGain) mic.setAutoGain(l.autoGain);
    if (l.deviceId !== prev.settings.listen.deviceId)
      mic.setDevice(l.deviceId).catch((e) => s.setListen({ error: e instanceof Error ? e.message : String(e) }));
    if (s.settings.view.theme !== prev.settings.view.theme) document.documentElement.dataset.theme = s.settings.view.theme;
    // Число струн доски = число струн инструмента.
    const strings = s.guitar().strings.length;
    if (s.board.length !== strings) store.setState({ board: emptyBoard(strings) });
  });

  // ---------- Аккорд на грифе → история (когда устоялся) и квинтовый круг ----------
  let historyTimer = 0;
  let lastSymbol = '';
  store.subscribe((s) => {
    const g = s.guitar();
    const p = g.result.kind === 'chord' ? g.result.primary : undefined;
    const sym = p?.symbol ?? '';
    if (sym === lastSymbol) return;
    lastSymbol = sym;
    window.clearTimeout(historyTimer);
    if (!p) return;
    s.pushTrail({ rootPc: p.rootPc, templateId: p.template.id, symbol: p.symbol, nameRu: p.nameRu, source: g.source });
    historyTimer = window.setTimeout(() => store.getState().recordHistory(), 800);
  });

  // ---------- Аккорд с гитары ----------
  bus.on('chord:heard', (c) => {
    const s = store.getState();
    s.notePlayedChord(c.symbol);
    // Пока открыт разбор песни, гриф и круг показывают только аккорды песни.
    if (s.songOpen > 0 || s.songPlaying) return;
    s.pushTrail({ rootPc: c.rootPc, templateId: c.templateId, symbol: c.symbol, nameRu: c.nameRu, source: 'guitar' });
    if (s.settings.listen.showOnBoard) s.showChord(c.rootPc, c.templateId, c.bassPc);
  });

  bus.on('notes:heard', (n) => {
    const s = store.getState();
    if (s.songOpen > 0 || s.songPlaying || !s.settings.listen.showOnBoard) return;
    const g = s.guitar();
    s.apply(boardFromMidi(n.midis, g.strings, g.capo), false);
  });

  // ---------- Время занятий ----------
  let lastInput = Date.now();
  const touch = () => (lastInput = Date.now());
  window.addEventListener('pointerdown', touch);
  window.addEventListener('keydown', touch);
  bus.on('mic:onset', touch);
  window.setInterval(() => {
    const s = store.getState();
    const busy = s.listen.active || s.seq.playing || s.metro.running || s.songPlaying || mic.active;
    if (document.visibilityState === 'visible' && (busy || Date.now() - lastInput < 60_000)) s.addPracticeSeconds(10);
  }, 10_000);

  // ---------- Горячие клавиши ----------
  window.addEventListener('keydown', (e) => {
    const tag = (e.target as HTMLElement).tagName;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      store.getState().setPaletteOpen(!store.getState().paletteOpen);
      return;
    }
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    const s = store.getState();
    if (e.code === 'Space') {
      e.preventDefault();
      s.play();
    } else if (e.key === 'Escape') {
      audio.stopAll();
      sequencer.stop();
    } else if (e.key === 'Delete' || e.key === 'Backspace') s.clearBoard();
    else if (e.key === 'ArrowRight') s.transpose(1);
    else if (e.key === 'ArrowLeft') s.transpose(-1);
  });

  // Файл, брошенный мимо зоны разбора песни, не должен открываться вместо программы.
  const prevent = (e: DragEvent) => e.preventDefault();
  window.addEventListener('dragover', prevent);
  window.addEventListener('drop', prevent);

  midiService.init();
  void s0;
  void chordListener;
  void metronome;
}
