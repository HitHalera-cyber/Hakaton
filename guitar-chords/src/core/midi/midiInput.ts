// MIDI через Web MIDI API (в Electron разрешение выдаёт главный процесс):
// приём нот с клавиатуры и вывод нот на внешнее устройство / в DAW.
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
  onDevicesChanged: (inputs: MidiDevice[], outputs: MidiDevice[]) => void;
  /** Педаль сустейна (CC 64). */
  onSustain?: (down: boolean) => void;
}

export class MidiInput {
  private access: MIDIAccess | null = null;
  private selected: string = ALL_DEVICES;
  private output: MIDIOutput | null = null;
  private outputId: string | null = null;

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

  outputs(): MidiDevice[] {
    if (!this.access?.outputs) return [];
    const list: MidiDevice[] = [];
    this.access.outputs.forEach((o) => {
      if (o.state === 'connected') list.push({ id: o.id, name: o.name ?? 'MIDI-выход', manufacturer: o.manufacturer ?? '' });
    });
    return list;
  }

  /** Выбрать MIDI-выход (null — не выводить). */
  selectOutput(id: string | null) {
    this.allNotesOff();
    this.outputId = id;
    this.output = id && this.access?.outputs ? (this.access.outputs.get(id) ?? null) : null;
  }

  get hasOutput(): boolean {
    return this.output != null;
  }

  /** Отправить ноту на выход: Note On через delaySec, Note Off через durationSec после него. */
  sendNote(midi: number, velocity: number, delaySec: number, durationSec: number, channel = 0) {
    if (!this.output) return;
    const t = performance.now() + delaySec * 1000;
    const vel = Math.max(1, Math.min(127, Math.round(velocity * 127)));
    try {
      this.output.send([0x90 | channel, midi, vel], t);
      this.output.send([0x80 | channel, midi, 0], t + durationSec * 1000);
    } catch {
      // устройство отключили — игнорируем
    }
  }

  allNotesOff() {
    try {
      this.output?.send([0xb0, 123, 0]);
    } catch {
      // устройство недоступно
    }
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
    if (this.outputId && this.access.outputs && !this.access.outputs.get(this.outputId)) this.output = null;
    else if (this.outputId && this.access.outputs) this.output = this.access.outputs.get(this.outputId) ?? null;
    this.handlers.onDevicesChanged(this.devices(), this.outputs());
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
