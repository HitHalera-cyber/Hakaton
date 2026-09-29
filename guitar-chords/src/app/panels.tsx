// Реестр разделов: как каждая панель из features/ получает данные из контекста приложения.

import type { ReactNode } from 'react';
import { audio } from '../core/audio/engine';
import { cellChord, circlePosition, type CirclePos } from '../core/music/circle';
import { boardFromMidi, emptyBoard } from '../core/music/fretboard';
import { SCALES } from '../core/music/scales';
import { CircleOfFifths } from '../features/circle/CircleOfFifths';
import { CirclePanel, resolveKey } from '../features/circle/CirclePanel';
import { FavoritesTab } from '../features/favorites/FavoritesTab';
import { KeyPanel } from '../features/key/KeyPanel';
import { LibraryPanel } from '../features/library/LibraryPanel';
import { ListenPanel } from '../features/listen/ListenPanel';
import { MetronomePanel } from '../features/metronome/MetronomePanel';
import { MidiPanel } from '../features/midi/MidiPanel';
import { ScalesPanel } from '../features/scales/ScalesPanel';
import { SequencerPanel } from '../features/sequencer/SequencerPanel';
import { SongPanel } from '../features/song/SongPanel';
import { SoundPanel } from '../features/sound/SoundPanel';
import { TrainerPanel } from '../features/trainer/TrainerPanel';
import { TunerPanel } from '../features/tuner/TunerPanel';
import { useApp, type App } from './AppContext';
import type { TabId } from './navigation';

function pickCircle(app: App, pos: CirclePos) {
  const c = cellChord(pos);
  const frets = app.guitar.voicingFor(c.rootPc, c.templateId);
  if (frets) app.guitar.loadFrets(frets);
}

export function circleProps(app: App) {
  const { trail } = app.circle;
  return {
    active: trail[0] ? circlePosition(trail[0].rootPc, trail[0].templateId) : null,
    pulseKey: trail[0]?.id,
    trail: trail.slice(1, 4).map((c) => circlePosition(c.rootPc, c.templateId)),
    keySel: resolveKey(app.settings.view.circleKey, trail).key,
    onPick: (pos: CirclePos) => pickCircle(app, pos),
  };
}

const PANELS: Record<TabId, (app: App) => ReactNode> = {
  sound: ({ settings, guitar }) => (
    <SoundPanel
      settings={settings.sound}
      instrument={guitar.tuning.instrument}
      onChange={settings.patchSound}
      onStrum={(dir) => {
        audio.stopAll(0.02);
        audio.strum(guitar.currentNotes(), dir);
      }}
      onArpeggio={() => {
        audio.stopAll(0.02);
        audio.arpeggio(guitar.currentNotes(), settings.sound.arpStepMs);
      }}
      onStop={() => audio.stopAll()}
      canPlay={guitar.activeMidi.length > 0}
    />
  ),

  sequence: (app) => (
    <SequencerPanel
      items={app.sequence}
      rhythm={app.settings.rhythm}
      onRhythm={app.settings.patchRhythm}
      playing={app.sequencer.playing}
      current={app.sequencer.current}
      canAdd={app.guitar.activeMidi.length > 0}
      onAdd={app.addCurrentToSequence}
      onChange={app.setSequence}
      onLoad={(it) => app.guitar.loadShape(it.board, app.settings.view.tuning, it.strings, it.capo)}
      onPlay={() => app.sequencer.play()}
      onStop={app.sequencer.stop}
      onExportMidi={() => app.exports.exportSequence(app.sequence, 'midi')}
      onExportTab={() => app.exports.exportSequence(app.sequence, 'tab')}
    />
  ),

  metronome: ({ settings }) => <MetronomePanel rhythm={settings.rhythm} onRhythm={settings.patchRhythm} />,

  listen: (app) => (
    <ListenPanel
      listener={app.listener}
      onPick={(c) => app.guitar.showChord(c.rootPc, c.templateId, c.bassPc)}
      voicing={(c) => app.guitar.voicingFor(c.rootPc, c.templateId, c.bassPc)}
      capo={app.guitar.capo}
      circle={<CircleOfFifths compact size={230} {...circleProps(app)} />}
    />
  ),

  song: (app) => (
    <SongPanel
      capo={app.guitar.capo}
      onCapo={app.guitar.setCapo}
      onChord={(c) => app.guitar.showChord(c.rootPc, c.templateId, c.bassPc)}
      onPlayingChange={app.setSongPlaying}
      onOpenChange={app.setSongOpen}
      onToast={app.showToast}
      onToSequence={(chords) => {
        const items = chords
          .map((c) => ({ symbol: c.symbol, beats: c.beats, frets: app.guitar.voicingFor(c.rootPc, c.templateId, c.bassPc) }))
          .filter((c): c is { symbol: string; beats: number; frets: NonNullable<typeof c.frets> } => c.frets != null);
        app.setSequence(app.itemsFromFrets(items));
        app.openTab('sequence');
        app.showToast(`В последовательность добавлено аккордов: ${items.length}`);
      }}
    />
  ),

  circle: (app) => (
    <CirclePanel
      trail={app.circle.trail}
      keyChoice={app.settings.view.circleKey}
      onKeyChoice={(circleKey) => app.settings.patchView({ circleKey })}
      listening={app.listener.active}
      onPick={(pos) => pickCircle(app, pos)}
      onClear={app.circle.clear}
    />
  ),

  library: ({ guitar, libRequest }) => (
    <LibraryPanel
      tuning={guitar.strings}
      capo={guitar.capo}
      current={guitar.chordRef}
      request={libRequest}
      onPick={(frets) => guitar.loadFrets(frets)}
    />
  ),

  scales: ({ settings, guitar }) => (
    <ScalesPanel
      settings={settings.scale}
      onChange={settings.patchScale}
      onPlay={(steps, rootPc) => {
        let start = Math.min(...guitar.strings) + guitar.capo;
        while (start % 12 !== rootPc) start++;
        const notes = [...steps.map((s) => start + s), start + 12];
        audio.stopAll(0.03);
        notes.forEach((m, i) => audio.playNote(m, 0.8, audio.now + i * 0.28, 'scale', 0.6));
      }}
    />
  ),

  key: (app) => (
    <KeyPanel
      tuning={app.guitar.strings}
      capo={app.guitar.capo}
      onPick={(frets) => app.guitar.loadFrets(frets)}
      onPlayProgression={(chords) => app.sequencer.play(app.itemsFromFrets(chords))}
      onToSequence={(chords) => {
        app.setSequence(app.itemsFromFrets(chords));
        app.openTab('sequence');
      }}
    />
  ),

  trainer: ({ guitar }) => (
    <TrainerPanel
      tuning={guitar.strings}
      capo={guitar.capo}
      soundingMidis={guitar.boardNotes.map((n) => n.midi)}
      registerCellHandler={guitar.registerCellHandler}
      setFlash={guitar.setFlash}
      loadFrets={(frets) => guitar.loadFrets(frets)}
      clearBoard={() => guitar.setBoard(emptyBoard(guitar.strings.length))}
    />
  ),

  tuner: ({ guitar }) => <TunerPanel tuning={guitar.strings} capo={guitar.capo} />,

  midi: ({ midi, guitar }) => (
    <MidiPanel
      status={midi.status}
      error={midi.error}
      devices={midi.devices}
      outputs={midi.outputs}
      selected={midi.opts.device}
      onSelect={(device) => midi.patchOpts({ device })}
      output={midi.opts.output}
      onOutput={(output) => midi.patchOpts({ output })}
      muteInternal={midi.opts.muteInternal}
      onMuteInternal={(muteInternal) => midi.patchOpts({ muteInternal })}
      active={midi.active}
      range={guitar.range}
      latch={midi.opts.latch}
      onLatch={(latch) => midi.patchOpts({ latch })}
      sound={midi.opts.sound}
      onSound={(sound) => midi.patchOpts({ sound })}
      onKey={midi.toggleKey}
      onClear={midi.clear}
      onRetry={midi.retry}
      onToBoard={() => {
        const notes = guitar.activeMidi;
        midi.clear();
        guitar.apply(boardFromMidi(notes, guitar.strings, guitar.capo));
      }}
    />
  ),

  favorites: ({ collections }) => <FavoritesTab collections={collections} />,
};

export function ToolPanel({ tab }: { tab: TabId }) {
  const app = useApp();
  return <>{PANELS[tab](app)}</>;
}

/** Подпись выбранной гаммы для кнопки над грифом. */
export function scaleTitle(scaleId: string): string {
  return (SCALES.find((s) => s.id === scaleId) ?? SCALES[0]).name.split(' (')[0].toLowerCase();
}
