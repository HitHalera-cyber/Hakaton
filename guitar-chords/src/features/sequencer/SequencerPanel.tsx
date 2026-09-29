import './sequencer.css';
import { PATTERNS } from '../../core/audio/patterns';
import type { RhythmSettings, SeqItem } from './useSequencer';
import { ChordDiagram } from '../fretboard/ChordDiagram';

interface Props {
  items: SeqItem[];
  rhythm: RhythmSettings;
  onRhythm: (patch: Partial<RhythmSettings>) => void;
  playing: boolean;
  current: number | null;
  canAdd: boolean;
  onAdd: () => void;
  onChange: (items: SeqItem[]) => void;
  onLoad: (item: SeqItem) => void;
  onPlay: () => void;
  onStop: () => void;
  onExportMidi: () => void;
  onExportTab: () => void;
}

export function SequencerPanel(p: Props) {
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= p.items.length) return;
    const next = [...p.items];
    [next[i], next[j]] = [next[j], next[i]];
    p.onChange(next);
  };
  const totalBeats = p.items.reduce((a, it) => a + it.beats, 0);

  return (
    <div className="tab-body">
      <div className="row">
        <button className="btn" onClick={p.onAdd} disabled={!p.canAdd} title="Добавить аккорд, который сейчас на грифе">
          ＋ Добавить аккорд с грифа
        </button>
        {p.items.length > 0 && (
          <button className="btn" onClick={() => p.onChange([])}>
            Очистить
          </button>
        )}
      </div>

      {p.items.length === 0 ? (
        <p className="hint">
          Поставьте аккорд на грифе и нажмите «Добавить», или выберите готовую последовательность на вкладке «Тональность».
        </p>
      ) : (
        <div className="seq-list">
          {p.items.map((it, i) => (
            <div key={it.id} className={`seq-item ${p.current === i ? 'playing' : ''}`}>
              <button className="seq-main" onClick={() => p.onLoad(it)} title="Показать на грифе">
                <span className="sym">{it.symbol}</span>
                <ChordDiagram frets={boardToFrets(it)} capo={it.capo} size={52} fingers={false} />
              </button>
              <select
                value={it.beats}
                onChange={(e) => p.onChange(p.items.map((x) => (x.id === it.id ? { ...x, beats: Number(e.target.value) } : x)))}
                title="Длительность в долях"
              >
                {[1, 2, 3, 4, 6, 8].map((b) => (
                  <option key={b} value={b}>
                    {b} {b === 1 ? 'доля' : b < 5 ? 'доли' : 'долей'}
                  </option>
                ))}
              </select>
              <div className="seq-actions">
                <button className="icon" onClick={() => move(i, -1)} title="Раньше">
                  ←
                </button>
                <button className="icon" onClick={() => move(i, 1)} title="Позже">
                  →
                </button>
                <button className="icon" onClick={() => p.onChange(p.items.filter((x) => x.id !== it.id))} title="Удалить">
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid2">
        <label className="field">
          <span>Схема боя</span>
          <select value={p.rhythm.patternId} onChange={(e) => p.onRhythm({ patternId: e.target.value })}>
            {PATTERNS.map((pt) => (
              <option key={pt.id} value={pt.id}>
                {pt.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Темп: {p.rhythm.bpm} ударов в минуту</span>
          <input type="range" min={40} max={200} value={p.rhythm.bpm} onChange={(e) => p.onRhythm({ bpm: Number(e.target.value) })} />
        </label>
      </div>
      <div className="row">
        <label className="check">
          <input type="checkbox" checked={p.rhythm.loop} onChange={(e) => p.onRhythm({ loop: e.target.checked })} />
          По кругу
        </label>
        <label className="check">
          <input type="checkbox" checked={p.rhythm.click} onChange={(e) => p.onRhythm({ click: e.target.checked })} />
          Метроном
        </label>
        {totalBeats > 0 && (
          <span className="hint">
            Всего: {totalBeats} долей ≈ {Math.round((totalBeats * 60) / p.rhythm.bpm)} с
          </span>
        )}
      </div>

      <div className="row">
        {p.playing ? (
          <button className="btn primary" onClick={p.onStop}>
            ■ Остановить
          </button>
        ) : (
          <button className="btn primary" onClick={p.onPlay} disabled={p.items.length === 0}>
            ▶ Играть последовательность
          </button>
        )}
        <button className="btn" onClick={p.onExportMidi} disabled={p.items.length === 0}>
          ⇩ MIDI-файл
        </button>
        <button className="btn" onClick={p.onExportTab} disabled={p.items.length === 0}>
          ⇩ Табулатура
        </button>
      </div>
    </div>
  );
}

function boardToFrets(it: SeqItem) {
  return it.board.map((s) => (s.muted ? null : s.frets.length ? Math.max(...s.frets) : s.open ? it.capo : null));
}
