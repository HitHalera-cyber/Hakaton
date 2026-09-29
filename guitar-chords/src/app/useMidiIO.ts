// MIDI-клавиатура (вход) и MIDI-выход: устройства, зажатые/зафиксированные ноты, экранная клавиатура.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { audio } from '../core/audio/engine';
import { ALL_DEVICES, MidiInput, type MidiDevice } from '../core/midi/midiInput';
import type { MidiStatus } from '../features/midi/MidiPanel';
import { useStored } from './useStored';

export interface MidiOptions {
  latch: boolean;
  sound: boolean;
  device: string;
  output: string;
  muteInternal: boolean;
}

export function useMidiIO() {
  const [opts, setOpts] = useStored<MidiOptions>('gc.midi', {
    latch: true,
    sound: true,
    device: ALL_DEVICES,
    output: '',
    muteInternal: false,
  });
  const [status, setStatus] = useState<MidiStatus>('init');
  const [error, setError] = useState<string>();
  const [devices, setDevices] = useState<MidiDevice[]>([]);
  const [outputs, setOutputs] = useState<MidiDevice[]>([]);
  const [held, setHeld] = useState<Set<number>>(new Set());
  const [latched, setLatched] = useState<Set<number>>(new Set());
  const heldRef = useRef(new Set<number>());
  const optsRef = useRef(opts);
  optsRef.current = opts;
  const midiRef = useRef<MidiInput | null>(null);

  const connect = useCallback((input: MidiInput) => {
    setStatus('init');
    input
      .init()
      .then(() => {
        input.select(optsRef.current.device);
        input.selectOutput(optsRef.current.output || null);
        setStatus('ready');
        setError(undefined);
      })
      .catch((e: unknown) => {
        const err = e instanceof Error ? e : new Error(String(e));
        // SecurityError / NotAllowedError — нет разрешения; InvalidStateError — нет драйвера MIDI в системе.
        setStatus(err.name === 'SecurityError' || err.name === 'NotAllowedError' ? 'denied' : 'unavailable');
        setError(err.message);
      });
  }, []);

  useEffect(() => {
    const input = new MidiInput({
      onNoteOn: (note, velocity) => {
        const wasEmpty = heldRef.current.size === 0;
        heldRef.current.add(note);
        setHeld(new Set(heldRef.current));
        // Новый аккорд начинается, когда все клавиши были отпущены.
        if (optsRef.current.latch) setLatched((prev) => (wasEmpty ? new Set([note]) : new Set(prev).add(note)));
        if (optsRef.current.sound) audio.playNote(note, velocity);
      },
      onNoteOff: (note) => {
        if (!heldRef.current.delete(note)) return;
        setHeld(new Set(heldRef.current));
      },
      onDevicesChanged: (ins, outs) => {
        setDevices(ins);
        setOutputs(outs);
      },
    });
    midiRef.current = input;
    if (!MidiInput.supported) {
      setStatus('unsupported');
      return;
    }
    connect(input);
    return () => input.dispose();
  }, [connect]);

  useEffect(() => midiRef.current?.select(opts.device), [opts.device]);
  useEffect(() => {
    midiRef.current?.selectOutput(opts.output || null);
    audio.onNoteOut = opts.output ? (m, v, d, dur) => midiRef.current?.sendNote(m, v, d, dur) : null;
    audio.muted = Boolean(opts.output && opts.muteInternal);
  }, [opts.output, opts.muteInternal]);

  const active = useMemo(() => new Set([...held, ...latched]), [held, latched]);

  const clear = useCallback(() => {
    setLatched(new Set());
    heldRef.current.clear();
    setHeld(new Set());
  }, []);

  /** Клик по экранной клавиатуре: добавить/убрать ноту. */
  const toggleKey = useCallback((m: number) => {
    setLatched((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else {
        next.add(m);
        audio.playNote(m, 0.8);
      }
      return next;
    });
  }, []);

  const shift = useCallback((k: number) => setLatched((prev) => new Set([...prev].map((m) => m + k))), []);
  const retry = useCallback(() => midiRef.current && connect(midiRef.current), [connect]);

  return {
    opts,
    patchOpts: (p: Partial<MidiOptions>) => {
      setOpts((o) => ({ ...o, ...p }));
      if (p.latch === false) setLatched(new Set());
    },
    status,
    error,
    devices,
    outputs,
    active,
    clear,
    toggleKey,
    shift,
    retry,
  };
}

export type MidiIO = ReturnType<typeof useMidiIO>;
