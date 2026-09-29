import './listen.css';
import type { DetectionResult } from '../../core/music/chords';
import type { Frets } from '../../core/music/fretboard';
import { pcName } from '../../core/music/notes';
import { ChordDiagram } from '../fretboard/ChordDiagram';
import type { RecognizedChord } from '../../core/analysis/chordRecognition';
import type { ChordListener } from './useChordListener';

interface Props {
  listener: ChordListener;
  /** Аккорд на грифе — показывается, пока гитару не слушаем. */
  board: DetectionResult;
  voicing: (chord: RecognizedChord) => Frets | null;
  capo: number;
}

/** Крупная «сцена» раскладки «Слушатель»: что слышно, насколько уверенно, какие ноты звучат. */
export function ListenerStage({ listener, board, voicing, capo }: Props) {
  const { active, error, level, result, chroma, hold, settings, patch } = listener;
  const best = result?.best;
  const holdMode = settings.mode === 'hold';
  const fallback = board.kind === 'chord' ? board.primary : undefined;
  const heard = listener.history[0];
  const frets = heard ? voicing(heard) : null;

  return (
    <section className="panel listener-stage">
      <div className="row">
        {active ? (
          <button className="btn" onClick={listener.stop}>
            ■ Перестать слушать
          </button>
        ) : (
          <button className="btn primary" onClick={listener.start}>
            👂 Начать слушать
          </button>
        )}
        <div className="segmented" role="radiogroup" aria-label="Режим">
          <button className={!holdMode ? 'on' : ''} onClick={() => patch({ mode: 'strum' })}>
            По удару
          </button>
          <button className={holdMode ? 'on' : ''} onClick={() => patch({ mode: 'hold' })}>
            Держите аккорд
          </button>
        </div>
        <label className="slider compact" title="Если программа плохо слышит гитару — прибавьте">
          <span>Усиление ×{settings.gain}</span>
          <input type="range" min={1} max={12} step={0.5} value={settings.gain} onChange={(e) => patch({ gain: Number(e.target.value) })} />
        </label>
      </div>
      {error && <p className="error">{error}</p>}

      <div className={`stage-chord ${best ? '' : 'idle'}`}>
        {frets && (
          <div className="listen-shape stage-shape" title={`Как играть ${heard!.symbol}`}>
            <small>Как играть {heard!.symbol}</small>
            <ChordDiagram frets={frets} capo={capo} size={120} />
          </div>
        )}
        {(best ?? fallback) && <div className="stage-symbol">{(best ?? fallback)!.symbol}</div>}
        <div className="stage-ru">
          {best
            ? `${best.nameRu} · ${Math.round(best.confidence * 100)}%`
            : fallback
              ? `${fallback.nameRu} — на грифе`
              : active
                ? 'Сыграйте аккорд'
                : 'Нажмите «Начать слушать» и сыграйте аккорд'}
        </div>
      </div>

      <div className="level stage-level" title="Уровень сигнала">
        <span style={{ width: `${level * 100}%` }} />
      </div>
      {holdMode && active && (
        <div className={`hold-bar ${hold.state}`}>
          <span style={{ width: `${Math.round(hold.progress * 100)}%` }} />
        </div>
      )}
      <div className="chroma-bars stage-bars" title="Какие ноты слышны">
        {chroma.map((v, i) => (
          <div key={i} className="cb">
            <span style={{ height: `${Math.round(v * 100)}%` }} />
            <small>{pcName(i)}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
