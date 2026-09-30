import { boardFromMidi } from '../../core/music/fretboard';
import { midiService } from '../../services/midi';
import { store, useGuitar, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { MidiPanel } from './MidiPanel';

function MidiView() {
  const s = usePick((s) => ({ io: s.midiIO, opts: s.settings.midi, patch: s.patchMidi, held: s.midiHeld, latched: s.midiLatched }));
  const g = useGuitar();
  const active = new Set([...s.held, ...s.latched]);
  return (
    <MidiPanel
      status={s.io.status}
      error={s.io.error}
      devices={s.io.devices}
      outputs={s.io.outputs}
      selected={s.opts.device}
      onSelect={(device) => s.patch({ device })}
      output={s.opts.output}
      onOutput={(output) => s.patch({ output })}
      muteInternal={s.opts.muteInternal}
      onMuteInternal={(muteInternal) => s.patch({ muteInternal })}
      active={active}
      range={g.range}
      latch={s.opts.latch}
      onLatch={(latch) => s.patch({ latch })}
      sound={s.opts.sound}
      onSound={(sound) => s.patch({ sound })}
      onKey={(m) => store.getState().toggleMidiKey(m)}
      onClear={() => store.getState().clearMidi()}
      onRetry={midiService.retry}
      onToBoard={() => {
        const st = store.getState();
        const notes = st.guitar().activeMidi;
        st.clearMidi();
        st.apply(boardFromMidi(notes, g.strings, g.capo));
      }}
    />
  );
}

export const midiModule: ModuleDef = {
  id: 'midi',
  title: 'MIDI',
  icon: '🎹',
  group: 'tools',
  description: 'MIDI-клавиатура: вход, выход и экранное пианино',
  keywords: ['клавиатура', 'пианино', 'синтезатор'],
  View: MidiView,
};
