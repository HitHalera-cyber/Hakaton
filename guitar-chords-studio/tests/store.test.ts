// Хранилище Studio проверяется без интерфейса: действия и производные данные — обычные функции.
import { beforeEach, describe, expect, it } from 'vitest';
import { store } from '../src/store';
import { bus } from '../src/services/bus';

const st = () => store.getState();

describe('хранилище: гриф и аккорд', () => {
  beforeEach(() => {
    st().patchSound({ autoPlay: false });
    st().clearMidi();
    st().patchView({ tuning: 'standard', capo: 0 });
  });

  it('аппликатура → определённый аккорд, транспонирование, каподастр', () => {
    st().loadFrets([null, 0, 2, 2, 1, 0], false);
    expect(st().guitar().result.primary?.symbol).toBe('Am');
    st().transpose(2);
    expect(st().guitar().result.primary?.symbol).toBe('Bm');
    st().setCapo(2);
    expect(st().guitar().capo).toBe(2);
  });

  it('MIDI-ноты важнее грифа, правка грифа их сбрасывает', () => {
    st().loadFrets([null, 3, 2, 0, 1, 0], false);
    st().midiNoteOn(60);
    st().midiNoteOn(64);
    st().midiNoteOn(67);
    expect(st().guitar().source).toBe('midi');
    expect(st().guitar().result.primary?.symbol).toBe('C');
    st().edit(st().board);
    expect(st().guitar().source).toBe('board');
  });

  it('производные данные запоминаются: без изменений — тот же объект', () => {
    expect(st().guitar()).toBe(st().guitar());
  });
});

describe('хранилище: песенник, практика, шина', () => {
  it('песня добавляется, правится и удаляется', () => {
    const id = st().addSong({ title: 'Тест', body: '[Am]раз' });
    expect(st().currentSongId).toBe(id);
    st().updateSong(id, { transpose: 2 });
    expect(st().songs.find((s) => s.id === id)?.transpose).toBe(2);
    st().removeSong(id);
    expect(st().songs.some((s) => s.id === id)).toBe(false);
  });

  it('аккорд считается выученным после 5 чистых повторов', () => {
    st().resetPractice();
    for (let i = 0; i < 4; i++) st().notePlayedChord('Em');
    expect(st().practice.learned).not.toContain('Em');
    st().notePlayedChord('Em');
    expect(st().practice.learned).toContain('Em');
  });

  it('рекорды обновляются только в лучшую сторону', () => {
    st().resetPractice();
    expect(st().setChangesBest('C→G', 20)).toBe(true);
    expect(st().setChangesBest('C→G', 15)).toBe(false);
    expect(st().setRhythmBest(40)).toBe(true);
    expect(st().setRhythmBest(55)).toBe(false);
  });

  it('шина событий доставляет и отписывает', () => {
    const got: string[] = [];
    const off = bus.on('chord:heard', (c) => got.push(c.symbol));
    bus.emit('chord:heard', { rootPc: 9, templateId: 'min', symbol: 'Am', nameRu: 'Ля минор', confidence: 1 } as never);
    off();
    bus.emit('chord:heard', { rootPc: 0, templateId: 'maj', symbol: 'C', nameRu: 'До мажор', confidence: 1 } as never);
    expect(got).toEqual(['Am']);
  });
});
