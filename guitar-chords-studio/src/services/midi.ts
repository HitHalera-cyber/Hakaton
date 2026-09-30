// MIDI-клавиатура (вход) и MIDI-выход: устройства и ноты идут в хранилище.

import { audio } from '../core/audio/engine';
import { MidiInput } from '../core/midi/midiInput';
import { store } from '../store';

let input: MidiInput | null = null;

function connect() {
  if (!input) return;
  const set = store.getState().setMidiIO;
  set({ status: 'init' });
  input
    .init()
    .then(() => {
      const o = store.getState().settings.midi;
      input!.select(o.device);
      input!.selectOutput(o.output || null);
      set({ status: 'ready', error: undefined });
    })
    .catch((e: unknown) => {
      const err = e instanceof Error ? e : new Error(String(e));
      // SecurityError / NotAllowedError — нет разрешения; InvalidStateError — нет драйвера MIDI в системе.
      set({ status: err.name === 'SecurityError' || err.name === 'NotAllowedError' ? 'denied' : 'unavailable', error: err.message });
    });
}

function applyOutput() {
  const o = store.getState().settings.midi;
  input?.selectOutput(o.output || null);
  audio.onNoteOut = o.output ? (m, v, d, dur) => input?.sendNote(m, v, d, dur) : null;
  audio.muted = Boolean(o.output && o.muteInternal);
}

export const midiService = {
  init() {
    input = new MidiInput({
      onNoteOn: (note, velocity) => {
        store.getState().midiNoteOn(note);
        if (store.getState().settings.midi.sound) audio.playNote(note, velocity);
      },
      onNoteOff: (note) => store.getState().midiNoteOff(note),
      onDevicesChanged: (devices, outputs) => store.getState().setMidiIO({ devices, outputs }),
    });
    if (!MidiInput.supported) return store.getState().setMidiIO({ status: 'unsupported' });
    connect();
    store.subscribe((s, prev) => {
      const a = s.settings.midi;
      const b = prev.settings.midi;
      if (a.device !== b.device) input?.select(a.device);
      if (a.output !== b.output || a.muteInternal !== b.muteInternal) applyOutput();
      if (!a.latch && b.latch) store.getState().clearMidi();
    });
    applyOutput();
  },
  retry: connect,
};
