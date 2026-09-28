import { useState } from 'react';
import type { Board } from '../music/fretboard';
import { TUNINGS, type TuningId } from '../music/tunings';

export interface HistoryEntry {
  id: string;
  symbol: string;
  nameRu: string;
  notes: string[];
  time: number;
  source: 'board' | 'midi';
  tuning: TuningId;
  board?: Board;
  midi?: number[];
}

export interface SavedShape {
  id: string;
  name: string;
  symbol: string;
  nameRu: string;
  tuning: TuningId;
  board: Board;
  created: number;
}

/** Табулатурная запись аппликатуры от 6-й к 1-й струне: «x32010». */
export function boardTab(board: Board): string {
  return board
    .map((s) => {
      if (s.muted) return 'x';
      const pos = [...(s.open ? [0] : []), ...s.frets];
      if (pos.length === 0) return '–';
      if (pos.length === 1) return String(pos[0]);
      return `(${pos.join(',')})`;
    })
    .join(' ');
}

const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' });

export function HistoryPanel({
  items,
  onPick,
  onClear,
}: {
  items: HistoryEntry[];
  onPick: (h: HistoryEntry) => void;
  onClear: () => void;
}) {
  return (
    <section className="panel list-panel">
      <h3>
        История
        {items.length > 0 && (
          <button className="link" onClick={onClear}>
            очистить
          </button>
        )}
      </h3>
      {items.length === 0 ? (
        <p className="hint">Здесь появятся определённые аккорды</p>
      ) : (
        <ul className="list">
          {items.map((h) => (
            <li key={h.id} onClick={() => onPick(h)} title={`${h.nameRu}\n${h.notes.join(' – ')}`}>
              <span className="sym">{h.symbol}</span>
              <span className="desc">{h.nameRu}</span>
              <span className="meta">
                {h.source === 'midi' ? 'MIDI' : 'гриф'} · {timeFmt.format(h.time)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SavedPanel({
  items,
  onPick,
  onDelete,
  onRename,
}: {
  items: SavedShape[];
  onPick: (s: SavedShape) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, name: string) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  return (
    <section className="panel list-panel">
      <h3>Избранные аппликатуры</h3>
      {items.length === 0 ? (
        <p className="hint">Нажмите «★ Сохранить», чтобы добавить текущую аппликатуру</p>
      ) : (
        <ul className="list">
          {items.map((s) => (
            <li key={s.id} onClick={() => editing !== s.id && onPick(s)} title={s.nameRu}>
              {editing === s.id ? (
                <input
                  autoFocus
                  className="rename"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onBlur={() => {
                    onRename(s.id, draft.trim() || s.symbol);
                    setEditing(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
                    if (e.key === 'Escape') setEditing(null);
                    e.stopPropagation();
                  }}
                />
              ) : (
                <span className="sym">{s.name}</span>
              )}
              <span className="desc tab">{boardTab(s.board)}</span>
              <span className="meta">
                {s.symbol !== s.name ? `${s.symbol} · ` : ''}
                {TUNINGS[s.tuning].id === 'dropD' ? 'Drop D' : 'Standard'}
              </span>
              <span className="item-actions">
                <button
                  className="icon"
                  title="Переименовать"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDraft(s.name);
                    setEditing(s.id);
                  }}
                >
                  ✎
                </button>
                <button
                  className="icon"
                  title="Удалить"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(s.id);
                  }}
                >
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
