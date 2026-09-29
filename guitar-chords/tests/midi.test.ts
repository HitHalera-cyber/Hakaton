import { describe, expect, it, vi } from 'vitest';
import { MidiInput } from '../src/core/midi/midiInput';

function fakeInput(id: string, name: string) {
  return { id, name, manufacturer: 'Test', state: 'connected', onmidimessage: null as null | ((e: unknown) => void) };
}

function setup() {
  const a = fakeInput('a', 'Keys A');
  const b = fakeInput('b', 'Keys B');
  const access = {
    inputs: new Map([
      ['a', a],
      ['b', b],
    ]),
    onstatechange: null as null | (() => void),
  };
  vi.stubGlobal('navigator', { requestMIDIAccess: vi.fn().mockResolvedValue(access) });
  const on: number[] = [];
  const off: number[] = [];
  const devices: string[][] = [];
  const midi = new MidiInput({
    onNoteOn: (n) => on.push(n),
    onNoteOff: (n) => off.push(n),
    onDevicesChanged: (d) => devices.push(d.map((x) => x.name)),
  });
  const send = (input: typeof a, bytes: number[]) => input.onmidimessage?.({ data: new Uint8Array(bytes) });
  return { a, b, access, midi, on, off, devices, send };
}

describe('MidiInput', () => {
  it('Note On / Note Off, включая Note On с velocity 0', async () => {
    const t = setup();
    await t.midi.init();
    t.send(t.a, [0x90, 60, 100]);
    t.send(t.a, [0x93, 64, 80]); // другой канал
    t.send(t.a, [0x80, 60, 0]);
    t.send(t.a, [0x90, 64, 0]);
    expect(t.on).toEqual([60, 64]);
    expect(t.off).toEqual([60, 64]);
    expect(t.devices.at(-1)).toEqual(['Keys A', 'Keys B']);
  });

  it('выбор одного устройства отключает остальные', async () => {
    const t = setup();
    await t.midi.init();
    t.midi.select('b');
    t.send(t.a, [0x90, 60, 100]);
    t.send(t.b, [0x90, 62, 100]);
    expect(t.on).toEqual([62]);
  });

  it('отключение устройства обновляет список', async () => {
    const t = setup();
    await t.midi.init();
    t.b.state = 'disconnected';
    t.access.onstatechange?.();
    expect(t.devices.at(-1)).toEqual(['Keys A']);
  });
});
