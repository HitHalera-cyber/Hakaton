import './songbook.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Frets } from '../../core/music/fretboard';
import { MAX_CAPO } from '../../core/music/tunings';
import { importChordsOverText, parseChordPro, songChords, transposeBody } from '../../core/songbook/chordpro';
import { planVoicings, voicingOptions } from '../../core/songbook/voicingPlan';
import { printSong } from '../../services/print';
import { store, useGuitar, usePick } from '../../store';
import type { Song } from '../../store/model';
import type { ModuleDef } from '../types';
import { ShapePicker } from './ShapePicker';
import { SongSheet } from './SongSheet';

/** Порядок аккордов в песне (для автоподбора переходов). */
const chordSequence = (body: string) => [...body.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1].trim());

function SongbookView() {
  const { songs, currentSongId, openSong, addSong, updateSong, removeSong } = usePick((s) => ({
    songs: s.songs,
    currentSongId: s.currentSongId,
    openSong: s.openSong,
    addSong: s.addSong,
    updateSong: s.updateSong,
    removeSong: s.removeSong,
  }));
  const g = useGuitar();
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [draft, setDraft] = useState({ title: '', text: '' });
  const [active, setActive] = useState<string>();
  const [scrolling, setScrolling] = useState(false);
  const [speed, setSpeed] = useState(18);
  const sheet = useRef<HTMLDivElement>(null);

  const song = songs.find((x) => x.id === currentSongId) ?? songs[0];
  const body = useMemo(() => (song ? transposeBody(song.body, song.transpose) : ''), [song]);
  const lines = useMemo(() => parseChordPro(body), [body]);
  const chords = useMemo(() => songChords(body), [body]);
  const filtered = songs.filter((x) => `${x.title} ${x.artist}`.toLowerCase().includes(query.toLowerCase()));

  // Автопрокрутка текста песни.
  useEffect(() => {
    if (!scrolling) return;
    let id = 0;
    let last = performance.now();
    let acc = 0;
    const tick = (t: number) => {
      const el = sheet.current;
      if (el) {
        acc += ((t - last) / 1000) * speed;
        last = t;
        const whole = Math.floor(acc);
        if (whole) {
          el.scrollTop += whole;
          acc -= whole;
        }
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 1) setScrolling(false);
      }
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [scrolling, speed]);

  if (!song) return <p className="hint">Песен пока нет.</p>;
  const patch = (p: Partial<Song>) => updateSong(song.id, p);

  const showChord = (symbol: string, frets?: Frets | null) => {
    setActive(symbol);
    const st = store.getState();
    if (st.guitar().capo !== song.capo) st.setCapo(song.capo);
    const f = frets ?? song.shapes[symbol] ?? voicingOptions(symbol, g.strings, song.capo, 1)[0]?.frets;
    if (f) st.loadFrets(f);
  };

  const autoPlan = () => {
    patch({ shapes: { ...song.shapes, ...planVoicings(chordSequence(body), g.strings, song.capo) } });
    store.getState().toast('Аппликатуры подобраны так, чтобы рука меньше двигалась между аккордами');
  };

  return (
    <div className="songbook-wrap">
      <div className="songbook">
        <aside className="sb-list no-print">
          <input className="sb-search" placeholder="Поиск песни…" value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="row">
            <button
              className="btn small primary"
              onClick={() => {
                addSong({ title: 'Новая песня', body: '{Куплет}\n[Am]Слова [F]песни' });
                setEditing(true);
              }}
            >
              ＋ Новая
            </button>
            <button
              className="btn small"
              onClick={() => setImporting((v) => !v)}
              title="Вставить песню с сайта: строки аккордов над строками текста"
            >
              ⇩ Вставить текст
            </button>
          </div>
          {filtered.map((x) => (
            <button key={x.id} className={`sb-item ${x.id === song.id ? 'on' : ''}`} onClick={() => (openSong(x.id), setEditing(false))}>
              <b>{x.title || 'Без названия'}</b>
              <small>{x.artist}</small>
            </button>
          ))}
        </aside>

        <section className="sb-main">
          {importing && (
            <div className="sb-import no-print">
              <input placeholder="Название песни" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              <textarea
                rows={8}
                placeholder={'Вставьте песню с сайта с аккордами, например:\nAm         F\nВот новый поворот'}
                value={draft.text}
                onChange={(e) => setDraft({ ...draft, text: e.target.value })}
              />
              <div className="row">
                <button
                  className="btn primary small"
                  disabled={!draft.text.trim()}
                  onClick={() => {
                    const b = importChordsOverText(draft.text);
                    const g2 = store.getState().guitar();
                    addSong({ title: draft.title || 'Песня', body: b, shapes: planVoicings(chordSequence(b), g2.strings, 0) });
                    setDraft({ title: '', text: '' });
                    setImporting(false);
                  }}
                >
                  Добавить песню
                </button>
                <span className="hint">Аккорды над строкой встанут в текст по своим местам.</span>
              </div>
            </div>
          )}

          <div className="sb-toolbar no-print">
            <button className={`btn small ${editing ? 'on' : ''}`} onClick={() => setEditing((v) => !v)}>
              {editing ? '✓ Готово' : '✎ Правка'}
            </button>
            <span className="sb-group" title="Транспонировать песню">
              Тон
              <button className="btn small" onClick={() => patch({ transpose: song.transpose - 1 })}>
                −½
              </button>
              <b>{song.transpose > 0 ? `+${song.transpose}` : song.transpose}</b>
              <button className="btn small" onClick={() => patch({ transpose: song.transpose + 1 })}>
                +½
              </button>
            </span>
            <label className="field inline" title="Каподастр для этой песни">
              <span>Каподастр</span>
              <select value={song.capo} onChange={(e) => patch({ capo: Number(e.target.value) })}>
                <option value={0}>нет</option>
                {Array.from({ length: MAX_CAPO }, (_, i) => i + 1).map((c) => (
                  <option key={c} value={c}>
                    {c} лад
                  </option>
                ))}
              </select>
            </label>
            <span className="sb-group" title="Автопрокрутка текста">
              <button className={`btn small ${scrolling ? 'on' : ''}`} onClick={() => setScrolling((v) => !v)}>
                {scrolling ? '❚❚ Прокрутка' : '▶ Прокрутка'}
              </button>
              <input type="range" min={4} max={60} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
            </span>
            <span className="grow" />
            <button className="btn small" onClick={autoPlan} title="Подобрать аппликатуры с самыми удобными переходами">
              🤚 Удобные переходы
            </button>
            <button className="btn small" onClick={() => printSong(song.title, 'print')}>
              🖨 Печать
            </button>
            <button className="btn small" onClick={() => printSong(song.title, 'pdf')}>
              PDF
            </button>
            <button
              className="btn small danger"
              onClick={() => {
                if (confirm(`Удалить песню «${song.title}»?`)) removeSong(song.id);
              }}
              title="Удалить песню"
            >
              🗑
            </button>
          </div>

          <div className="print-root">
            {editing ? (
              <div className="sb-edit no-print">
                <div className="row">
                  <input value={song.title} onChange={(e) => patch({ title: e.target.value })} placeholder="Название" />
                  <input value={song.artist} onChange={(e) => patch({ artist: e.target.value })} placeholder="Исполнитель" />
                </div>
                <textarea rows={16} value={song.body} onChange={(e) => patch({ body: e.target.value })} spellCheck={false} />
                <p className="hint">
                  Аккорд — в квадратных скобках перед слогом: <code>[Am]Вот новый [F]поворот</code>. Раздел — в фигурных:{' '}
                  <code>{'{Припев}'}</code>.
                </p>
              </div>
            ) : (
              <>
                <header className="sb-head">
                  <b className="sb-title">{song.title}</b>
                  {song.artist && <span>{song.artist}</span>}
                  {song.capo > 0 && <span className="sb-capo">Каподастр: {song.capo} лад</span>}
                  {song.transpose !== 0 && <span className="sb-capo no-print">Тональность сдвинута на {song.transpose} пт.</span>}
                </header>
                <ShapePicker
                  chords={chords}
                  shapes={song.shapes}
                  strings={g.strings}
                  capo={song.capo}
                  onChoose={(c, frets) => patch({ shapes: { ...song.shapes, [c]: frets } })}
                  onShow={(c, frets) => showChord(c, frets)}
                />
                <div className="sb-scroll" ref={sheet}>
                  <SongSheet lines={lines} active={active} onChord={(c) => showChord(c)} />
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export const songbookModule: ModuleDef = {
  id: 'songbook',
  title: 'Песенник',
  icon: '📒',
  group: 'songs',
  description: 'Песни с аккордами над текстом, прокрутка, транспонирование, печать и PDF',
  keywords: ['песня', 'текст', 'аккорды над текстом', 'печать', 'pdf', 'прокрутка', 'транспонировать'],
  View: SongbookView,
  isNew: true,
};
