import '../../ui/practice.css';
import { useRef, useState } from 'react';
import { MelodyTracker, melodyTab, placeOnFretboard, type MelodyNote } from '../../core/analysis/melody';
import { audio } from '../../core/audio/engine';
import { copyText } from '../../core/export/download';
import { boardFromFrets } from '../../core/music/fretboard';
import { midiName, pcNameRu } from '../../core/music/notes';
import { OnsetDetector } from '../../services/mic';
import { usePitch } from '../../services/usePitch';
import { store, useGuitar } from '../../store';
import type { ModuleDef } from '../types';

/** Подбор мелодии: играете или напеваете — программа записывает ноты и строит табулатуру. */
function MelodyView() {
  const g = useGuitar();
  const [notes, setNotes] = useState<MelodyNote[]>([]);
  const tracker = useRef(new MelodyTracker());
  const onsets = useRef(new OnsetDetector(0.55, 0.12));
  const pitch = usePitch((r, level, time) => {
    const onset = onsets.current.feed(level, time);
    tracker.current.feed(r ? r.midi : null, time, onset);
    if (tracker.current.notes.length !== notes.length) setNotes([...tracker.current.notes]);
  });

  const stop = () => {
    tracker.current.flush();
    setNotes([...tracker.current.notes]);
    pitch.stop();
  };
  const clear = () => {
    tracker.current = new MelodyTracker();
    setNotes([]);
  };
  const midis = notes.map((n) => n.midi);
  const tab = midis.length ? melodyTab(midis, g.strings, g.capo) : '';

  const playBack = () => {
    audio.stopAll(0.02);
    const t0 = notes[0]?.start ?? 0;
    for (const n of notes) audio.playNote(n.midi, 0.85, audio.now + 0.05 + (n.start - t0), undefined, Math.max(0.15, n.end - n.start));
  };

  /** Показать ноту на грифе — там, где её предлагает табулатура. */
  const showNote = (i: number) => {
    const pos = placeOnFretboard(midis, g.strings, g.capo)[i];
    audio.playNote(midis[i], 0.9);
    if (!pos) return;
    const frets = g.strings.map((_, s) => (s === pos.string ? pos.fret : null));
    store.getState().setBoard(boardFromFrets(frets, g.capo));
  };

  return (
    <div className="tab-body">
      <p className="hint">Сыграйте мелодию по одной ноте (или напойте) — ноты появятся ниже, а под ними табулатура для гитары.</p>
      <div className="pr-row">
        {pitch.active ? (
          <button className="btn" onClick={stop}>
            ■ Стоп
          </button>
        ) : (
          <button className="btn primary" onClick={pitch.start}>
            🎤 Записывать
          </button>
        )}
        <button className="btn" disabled={!notes.length} onClick={playBack}>
          ▶ Проиграть
        </button>
        <button className="btn" disabled={!notes.length || pitch.active} onClick={clear}>
          Очистить
        </button>
        {pitch.active && (
          <div className="level" title="Уровень микрофона">
            <span style={{ width: `${pitch.level * 100}%` }} />
          </div>
        )}
      </div>
      {pitch.error && <p className="error">{pitch.error}</p>}

      <div className="pr-row">
        <div className="pr-target">
          <span className="sym">{pitch.reading ? midiName(pitch.reading.midi) : '—'}</span>
          <small className="hint">{pitch.reading ? pcNameRu(pitch.reading.midi) : pitch.active ? 'играйте…' : 'сейчас звучит'}</small>
        </div>
        <div className="pr-card">
          <small>Нот записано</small>
          <b>{notes.length}</b>
        </div>
      </div>

      {notes.length > 0 && (
        <>
          <div className="pr-chips" title="Клик — показать ноту на грифе">
            {notes.map((n, i) => (
              <button key={i} onClick={() => showNote(i)}>
                {midiName(n.midi)}
              </button>
            ))}
          </div>
          <pre className="pr-pre">{tab}</pre>
          <div className="pr-row">
            <button
              className="btn small"
              onClick={() =>
                void copyText(tab).then((ok) => store.getState().toast(ok ? 'Табулатура скопирована' : 'Не удалось скопировать'))
              }
            >
              ⧉ Копировать табулатуру
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export const melodyModule: ModuleDef = {
  id: 'melody',
  title: 'Подбор мелодии (прототип)',
  icon: '🎶',
  group: 'modes',
  description: 'Напойте или сыграйте мелодию — программа запишет ноты и табулатуру',
  keywords: ['мелодия', 'ноты', 'табулатура', 'напеть', 'соло', 'рифф'],
  View: MelodyView,
};
