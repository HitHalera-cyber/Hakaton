import { chordsToBars } from '../../core/songbook/chordpro';
import { planVoicings } from '../../core/songbook/voicingPlan';
import { store, useGuitar } from '../../store';
import type { ModuleDef } from '../types';
import { SongPanel } from './SongPanel';

const st = () => store.getState();

function SongView() {
  const g = useGuitar();
  return (
    <SongPanel
      capo={g.capo}
      onCapo={(c) => st().setCapo(c)}
      onChord={(c) => {
        st().showChord(c.rootPc, c.templateId, c.bassPc);
        st().pushTrail({ rootPc: c.rootPc, templateId: c.templateId, symbol: c.symbol, nameRu: c.symbol, source: 'song' });
      }}
      onPlayingChange={(v) => st().setSongPlaying(v)}
      onOpenChange={(v) => st().setSongOpen(v)}
      onToast={(t) => st().toast(t)}
      onToSequence={(chords) => {
        const items = chords
          .map((c) => ({ symbol: c.symbol, beats: c.beats, frets: st().voicingFor(c.rootPc, c.templateId, c.bassPc) }))
          .filter((c): c is { symbol: string; beats: number; frets: NonNullable<typeof c.frets> } => c.frets != null);
        st().setSequence(st().itemsFromFrets(items));
        st().openModule('sequence');
        st().toast(`В последовательность добавлено аккордов: ${items.length}`);
      }}
      onToSongbook={(chords, info) => {
        const body = `{Аккорды по тактам (из разбора)}\n${chordsToBars(chords)}\n\n{Текст}\nВставьте сюда слова песни и расставьте аккорды: [Am]слово`;
        const g2 = st().guitar();
        st().addSong({
          title: info.title,
          artist: 'Разбор песни',
          body,
          bpm: info.bpm,
          capo: info.capo,
          shapes: planVoicings(
            chords.map((c) => c.symbol),
            g2.strings,
            info.capo,
          ),
        });
        st().openModule('songbook');
        st().toast('Песня добавлена в песенник');
      }}
    />
  );
}

export const songModule: ModuleDef = {
  id: 'song',
  title: 'Разбор песни (прототип)',
  icon: '🎧',
  group: 'modes',
  description: 'Аккорды из аудиофайла, замедление, повтор A–B, без вокала, в песенник',
  keywords: ['mp3', 'аудио', 'подобрать', 'замедлить', 'вокал', 'бас', 'повтор'],
  View: SongView,
};
