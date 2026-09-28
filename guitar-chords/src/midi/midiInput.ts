// Приём MIDI через Web MIDI API (в Electron разрешение выдаёт главный процесс).
// Обрабатываются стандартные сообщения Note On (0x9n) и Note Off (0x8n);
// Note On с velocity 0 трактуется как Note Off. Устройства отслеживаются «на лету».

export interface MidiDevice {
  id: string;
  name: string;
  manufacturer: string;
}

export const ALL_DEVICES = 'all';

export interface MidiHandlers {
  onNoteOn: (note: number, velocity: number) => void;
  onNoteOff: (note: number) => void;
  onDevicesChanged: (devices: MidiDevice[]) => void;
  /** Педаль сустейна (CC 64). */
  onSustain?: (down: boolean) => void;
}

export class MidiInput {
  private access: MIDIAccess | null = null;
  private selected: string = ALL_DEVICES;

  constructor(private handlers: MidiHandlers) {}

  static get supported(): boolean {
    return typeof navigator !== 'undefined' && 'requestMIDIAccess' in navigator;
  }

  async init(): Promise<void> {
    if (!MidiInput.supported) throw new Error('Web MIDI не поддерживается в этой среде');
    this.access = await navigator.requestMIDIAccess({ sysex: false });
    this.access.onstatechange = () => this.refresh();
    this.refresh();
  }

  devices(): MidiDevice[] {
    if (!this.access) return [];
    const list: MidiDevice[] = [];
    this.access.inputs.forEach((input) => {
      if (input.state === 'connected') {
        list.push({ id: input.id, name: input.name ?? 'MIDI-устройство', manufacturer: input.manufacturer ?? '' });
      }
    });
    return list;
  }

  select(id: string) {
    this.selected = id;
    this.refresh();
  }

  private refresh() {
    if (!this.access) return;
    this.access.inputs.forEach((input) => {
      const listen = this.selected === ALL_DEVICES || this.selected === input.id;
      input.onmidimessage = listen ? (e) => this.handle(e) : null;
    });
    this.handlers.onDevicesChanged(this.devices());
  }

  private handle(e: MIDIMessageEvent) {
    const data = e.data;
    if (!data || data.length < 3) return;
    const status = data[0] & 0xf0;
    const d1 = data[1];
    const d2 = data[2];
    if (status === 0x90 && d2 > 0) this.handlers.onNoteOn(d1, d2 / 127);
    else if (status === 0x80 || (status === 0x90 && d2 === 0)) this.handlers.onNoteOff(d1);
    else if (status === 0xb0 && d1 === 64) this.handlers.onSustain?.(d2 >= 64);
    else if (status === 0xb0 && (d1 === 123 || d1 === 120)) {
      // All Notes Off / All Sound Off
      for (let n = 0; n < 128; n++) this.handlers.onNoteOff(n);
    }
  }

  dispose() {
    if (!this.access) return;
    this.access.onstatechange = null;
    this.access.inputs.forEach((input) => (input.onmidimessage = null));
    this.access = null;
  }
}
