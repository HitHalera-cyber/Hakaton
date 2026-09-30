// Песенник: песни с аккордами над текстом.

import { uid, type Song } from './model';
import type { Slice } from './types';

export interface SongbookSlice {
  songs: Song[];
  currentSongId: string | null;
  addSong: (p: Partial<Song>) => string;
  updateSong: (id: string, p: Partial<Song>) => void;
  removeSong: (id: string) => void;
  openSong: (id: string | null) => void;
}

export const DEMO_SONG: Song = {
  id: 'demo',
  title: 'Пример: как записывать песню',
  artist: 'Песенник',
  body: `{Куплет}
[Am]Аккорд пишется в [F]квадратных скобках
[C]прямо перед слогом, на [G]котором он звучит.
[Am]Нажмите на аккорд — он [F]встанет на гриф,
[C]а «Прокрутка» сама [E]листает текст.

{Припев}
[F]Можно вставить песню [G]с сайта с аккордами:
[C]строка аккордов над [Am]строкой текста
[Dm]сама превратится в [E]такую запись.`,
  capo: 0,
  bpm: 90,
  transpose: 0,
  shapes: {},
  created: 0,
  updated: 0,
};

export const createSongbookSlice: Slice<SongbookSlice> = (set, get) => ({
  songs: [DEMO_SONG],
  currentSongId: 'demo',
  addSong: (p) => {
    const now = Date.now();
    const song: Song = { ...DEMO_SONG, title: 'Новая песня', artist: '', body: '', ...p, id: uid(), created: now, updated: now };
    set((s) => ({ songs: [song, ...s.songs], currentSongId: song.id }));
    return song.id;
  },
  updateSong: (id, p) => set((s) => ({ songs: s.songs.map((x) => (x.id === id ? { ...x, ...p, updated: Date.now() } : x)) })),
  removeSong: (id) =>
    set((s) => {
      const songs = s.songs.filter((x) => x.id !== id);
      return { songs, currentSongId: s.currentSongId === id ? (songs[0]?.id ?? null) : s.currentSongId };
    }),
  openSong: (currentSongId) => {
    set({ currentSongId });
    void get;
  },
});
