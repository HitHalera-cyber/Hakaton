import './listen.css';
import type { ReactNode } from 'react';
import type { RecognizedChord } from '../../core/analysis/chordRecognition';
import type { Frets } from '../../core/music/fretboard';
import { pcName } from '../../core/music/notes';
import { ChordDiagram } from '../../ui/ChordDiagram';
import type { ChordListener } from './useListener';

interface Props {
  listener: ChordListener;
  /** Клик по аккорду в истории — показать его на грифе. */
  onPick: (chord: RecognizedChord) => void;
  /** Квинтовый круг рядом с результатом. */
  circle?: ReactNode;
  /** Аппликатура аккорда — для схемы «как играть». */
  voicing: (chord: RecognizedChord) => Frets | null;
  capo: number;
}

const HOLD_TEXT = {
  idle: 'Возьмите аккорд и держите его звучание',
  listening: 'Слушаю… держите аккорд',
  done: 'Готово! Заглушите струны или сыграйте следующий аккорд',
  short: 'Держите аккорд подольше — звук оборвался слишком рано',
};

export function ListenPanel({ listener, onPick, circle, voicing, capo }: Props) {
  const { active, error, level, result, chroma, history, hold, settings, patch } = listener;
  const best = result?.best;
  const holdMode = settings.mode === 'hold';
  const pending = holdMode && hold.state === 'listening';
  // Схема — для последнего распознанного аккорда (он же показан на грифе).
  const heard = history[0];
  const frets = heard ? voicing(heard) : null;

  return (
    <div className="tab-body">
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
          <button className={!holdMode ? 'on' : ''} onClick={() => patch({ mode: 'strum' })} title="Аккорд определяется сразу после удара">
            По удару
          </button>
          <button
            className={holdMode ? 'on' : ''}
            onClick={() => patch({ mode: 'hold' })}
            title="Держите аккорд несколько секунд — результат точнее"
          >
            Держите аккорд
          </button>
        </div>
        {active && (
          <div className="level" title="Уровень сигнала (с учётом усиления). Если полоска едва видна — прибавьте усиление">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className="listen-main">
        <div className={`listen-result ${active ? '' : 'off'} ${pending ? 'pending' : ''}`}>
          {best ? (
            <>
              <div className="listen-symbol">{best.symbol}</div>
              <div className="listen-ru">{best.nameRu}</div>
              {!pending && (
                <div className="confidence" title="Насколько программа уверена">
                  <span
                    style={{ width: `${Math.round(best.confidence * 100)}%` }}
                    className={best.confidence > 0.6 ? 'hi' : best.confidence > 0.35 ? 'mid' : 'lo'}
                  />
                  <b>{Math.round(best.confidence * 100)}%</b>
                </div>
              )}
              {!pending && result!.alternatives.length > 0 && (
                <div className="chord-alts">
                  <span className="muted-label">Или:</span>
                  {result!.alternatives.map((a) => (
                    <span key={a.symbol} className="alt" title={a.nameRu}>
                      {a.symbol}
                    </span>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="hint center">
              {active
                ? holdMode
                  ? HOLD_TEXT.idle
                  : 'Сыграйте аккорд — один удар по всем струнам'
                : 'Нажмите «Начать слушать» и сыграйте аккорд на гитаре'}
            </div>
          )}
          {holdMode && active && (
            <div className={`hold-bar ${hold.state}`}>
              <span style={{ width: `${Math.round(hold.progress * 100)}%` }} />
              <small>{HOLD_TEXT[hold.state]}</small>
            </div>
          )}
        </div>
        {frets && (
          <div className="listen-shape" title={`Как играть ${heard!.symbol} — этот аккорд показан и на грифе`}>
            <small>Как играть {heard!.symbol}</small>
            <ChordDiagram frets={frets} capo={capo} size={110} />
          </div>
        )}
        {circle}
      </div>

      <div className="chroma-bars" title="Какие ноты слышны">
        {chroma.map((v, i) => (
          <div key={i} className="cb">
            <span style={{ height: `${Math.round(v * 100)}%` }} />
            <small>{pcName(i)}</small>
          </div>
        ))}
      </div>

      <div className="listen-settings">
        <label className="slider">
          <span>Усиление микрофона ×{settings.gain}</span>
          <input type="range" min={1} max={12} step={0.5} value={settings.gain} onChange={(e) => patch({ gain: Number(e.target.value) })} />
        </label>
        {holdMode ? (
          <label className="slider">
            <span>Сколько держать аккорд: {settings.holdSeconds.toFixed(1)} с</span>
            <input
              type="range"
              min={1}
              max={5}
              step={0.5}
              value={settings.holdSeconds}
              onChange={(e) => patch({ holdSeconds: Number(e.target.value) })}
            />
          </label>
        ) : (
          <label className="slider">
            <span>Чувствительность к удару</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.sensitivity}
              onChange={(e) => patch({ sensitivity: Number(e.target.value) })}
            />
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={settings.showOnBoard} onChange={(e) => patch({ showOnBoard: e.target.checked })} />
          Повторять аккорд на грифе
        </label>
      </div>

      {history.length > 0 && (
        <div className="listen-history">
          <span className="muted-label">Сыграно:</span>
          {history.map((h, i) => (
            <button key={i} className="alt" onClick={() => onPick(h)} title={h.nameRu}>
              {h.symbol}
            </button>
          ))}
          <button className="link" onClick={listener.clearHistory}>
            очистить
          </button>
        </div>
      )}
      <p className="hint">
        Микрофон в 30–50 см от гитары, тихая комната. Если программа «не слышит» — прибавьте усиление, чтобы полоска уровня доходила хотя бы
        до трети. «Держите аккорд» точнее «По удару», особенно при тихой игре.
      </p>
    </div>
  );
}
