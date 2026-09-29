// Запись стандартного MIDI-файла (SMF type 0) — для экспорта аккорда или последовательности.

export interface MidiNoteEvent {
  midi: number;
  /** Начало в долях (четвертях). */
  start: number;
  /** Длительность в долях. */
  duration: number;
  velocity: number;
}

const PPQ = 480;

function varLen(n: number): number[] {
  const bytes = [n & 0x7f];
  n >>= 7;
  while (n > 0) {
    bytes.unshift((n & 0x7f) | 0x80);
    n >>= 7;
  }
  return bytes;
}

const u32 = (n: number) => [(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
const u16 = (n: number) => [(n >> 8) & 0xff, n & 0xff];
const ascii = (s: string) => [...s].map((c) => c.charCodeAt(0));

/** GM-программы: 24 нейлон, 25 сталь, 27 электро чистый, 29 перегруз, 33 бас. */
export function writeMidiFile(notes: MidiNoteEvent[], bpm: number, program: number, name = 'GuitarChords'): Uint8Array<ArrayBuffer> {
  const events: { tick: number; data: number[] }[] = [];
  for (const n of notes) {
    const on = Math.round(n.start * PPQ);
    const off = Math.round((n.start + n.duration) * PPQ);
    const vel = Math.max(1, Math.min(127, Math.round(n.velocity * 127)));
    events.push({ tick: on, data: [0x90, n.midi, vel] });
    events.push({ tick: off, data: [0x80, n.midi, 0] });
  }
  // Note Off раньше Note On в одном тике — чтобы повторные ноты не обрывались.
  events.sort((a, b) => a.tick - b.tick || a.data[0] - b.data[0]);

  const track: number[] = [];
  const nameBytes = [...new TextEncoder().encode(name)];
  track.push(0, 0xff, 0x03, ...varLen(nameBytes.length), ...nameBytes);
  const mpqn = Math.round(60_000_000 / bpm);
  track.push(0, 0xff, 0x51, 0x03, (mpqn >> 16) & 0xff, (mpqn >> 8) & 0xff, mpqn & 0xff);
  track.push(0, 0xff, 0x58, 0x04, 4, 2, 24, 8);
  track.push(0, 0xc0, program & 0x7f);
  let last = 0;
  for (const e of events) {
    track.push(...varLen(e.tick - last), ...e.data);
    last = e.tick;
  }
  track.push(0, 0xff, 0x2f, 0x00);

  return new Uint8Array([...ascii('MThd'), ...u32(6), ...u16(0), ...u16(1), ...u16(PPQ), ...ascii('MTrk'), ...u32(track.length), ...track]);
}
