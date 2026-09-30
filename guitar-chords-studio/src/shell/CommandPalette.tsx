import { useEffect, useMemo, useRef, useState } from 'react';
import { parseChordSymbol } from '../core/music/chordParse';
import { MODULES } from '../modules/registry';
import { store, usePick } from '../store';
import { LAYOUTS } from './layouts/list';
import { THEMES } from './themes';

interface Item {
  id: string;
  icon: string;
  title: string;
  hint: string;
  words: string;
  run: () => void;
}

/** Панель команд (Ctrl+K): разделы, песни, аккорды, темы и раскладки — по реестру и хранилищу. */
export function CommandPalette() {
  const { open, setOpen, songs } = usePick((s) => ({ open: s.paletteOpen, setOpen: s.setPaletteOpen, songs: s.songs }));
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ('');
      setSel(0);
      window.setTimeout(() => input.current?.focus(), 0);
    }
  }, [open]);

  const items = useMemo(() => {
    const st = store.getState();
    const list: Item[] = [
      ...MODULES.map((m) => ({
        id: `m-${m.id}`,
        icon: m.icon,
        title: m.title,
        hint: m.description,
        words: [m.title, m.description, ...(m.keywords ?? [])].join(' '),
        run: () => st.openModule(m.id),
      })),
      ...songs.map((s) => ({
        id: `s-${s.id}`,
        icon: '📒',
        title: s.title,
        hint: `Песня${s.artist ? ` · ${s.artist}` : ''}`,
        words: `${s.title} ${s.artist} песня`,
        run: () => {
          st.openSong(s.id);
          st.openModule('songbook');
        },
      })),
      ...THEMES.map((t) => ({
        id: `t-${t.id}`,
        icon: '🎨',
        title: `Тема: ${t.name}`,
        hint: t.description,
        words: `тема оформление ${t.name}`,
        run: () => st.patchView({ theme: t.id }),
      })),
      ...LAYOUTS.map((l) => ({
        id: `l-${l.id}`,
        icon: '▦',
        title: `Раскладка: ${l.name}`,
        hint: l.description,
        words: `раскладка ${l.name}`,
        run: () => st.patchView({ layout: l.id }),
      })),
    ];
    const chord = parseChordSymbol(q);
    if (chord) {
      list.unshift({
        id: 'chord',
        icon: '🎸',
        title: `Аккорд ${chord.symbol} на гриф`,
        hint: chord.nameRu,
        words: q,
        run: () => {
          const frets = st.voicingFor(chord.rootPc, chord.template.id, chord.bassPc);
          if (frets) st.loadFrets(frets);
        },
      });
    }
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    // Сначала — совпадения в начале названия, потом в названии, потом в описании и ключевых словах.
    const rank = (it: Item) => {
      if (it.id === 'chord') return -1;
      const t = it.title.toLowerCase();
      return words.every((w) => t.startsWith(w)) ? 0 : words.every((w) => t.includes(w)) ? 1 : 2;
    };
    return list
      .filter((it) => it.id === 'chord' || words.every((w) => it.words.toLowerCase().includes(w)))
      .sort((a, b) => rank(a) - rank(b))
      .slice(0, 12);
  }, [q, songs]);

  if (!open) return null;
  const run = (it: Item | undefined) => {
    if (!it) return;
    setOpen(false);
    it.run();
  };

  return (
    <div className="palette-backdrop" onClick={() => setOpen(false)}>
      <div className="palette panel" onClick={(e) => e.stopPropagation()}>
        <input
          ref={input}
          autoFocus
          value={q}
          placeholder="Раздел, песня, аккорд (Am7, F#m…), тема…"
          onChange={(e) => {
            setQ(e.target.value);
            setSel(0);
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') setSel((i) => Math.min(items.length - 1, i + 1));
            else if (e.key === 'ArrowUp') setSel((i) => Math.max(0, i - 1));
            else if (e.key === 'Enter') run(items[sel]);
            else if (e.key === 'Escape') setOpen(false);
            else return;
            e.preventDefault();
          }}
        />
        <div className="palette-list">
          {items.map((it, i) => (
            <button key={it.id} className={i === sel ? 'on' : ''} onMouseEnter={() => setSel(i)} onClick={() => run(it)}>
              <span className="p-icon">{it.icon}</span>
              <b>{it.title}</b>
              <small>{it.hint}</small>
            </button>
          ))}
          {!items.length && <p className="hint">Ничего не нашлось</p>}
        </div>
      </div>
    </div>
  );
}
