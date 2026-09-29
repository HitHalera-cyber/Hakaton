import type { ReactNode } from 'react';
import type { RecognizedChord } from '../music/chordRecognition';
import { pcName } from '../music/notes';
import type { ChordListener } from '../state/useChordListener';

interface Props {
  listener: ChordListener;
  /** Клик по аккорду в истории — показать его на грифе. */
  onPick: (chord: RecognizedChord) => void;
  /** Квинтовый круг рядом с результатом. */
  circle?: ReactNode;
}

export function ListenPanel({ listener, onPick, circle }: Props) {
  const { active, error, level, result, chroma, history, showOnBoard, sensitivity } = listener;
  const best = result?.best;
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
        {active && (
          <div className="level" title="Уровень сигнала с микрофона">
            <span style={{ width: `${level * 100}%` }} />
          </div>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      <div className="listen-main">
      <div className={`listen-result ${active ? '' : 'off'}`}>
        {best ? (
          <>
            <div className="listen-symbol">{best.symbol}</div>
            <div className="listen-ru">{best.nameRu}</div>
            <div className="confidence" title="Насколько программа уверена">
              <span style={{ width: `${Math.round(best.confidence * 100)}%` }} className={best.confidence > 0.6 ? 'hi' : best.confidence > 0.35 ? 'mid' : 'lo'} />
              <b>{Math.round(best.confidence * 100)}%</b>
            </div>
            {result!.alternatives.length > 0 && (
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
          <div className="hint center">{active ? 'Сыграйте аккорд — один удар по всем струнам' : 'Нажмите «Начать слушать» и сыграйте аккорд на гитаре'}</div>
        )}
      </div>

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

      <div className="row">
        <label className="check">
          <input type="checkbox" checked={showOnBoard} onChange={(e) => listener.setShowOnBoard(e.target.checked)} />
          Показывать аккорд на грифе
        </label>
        <label className="slider grow">
          <span>Чувствительность к удару</span>
          <input type="range" min={0} max={1} step={0.05} value={sensitivity} onChange={(e) => listener.setSensitivity(Number(e.target.value))} />
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
        Лучше всего: тихая комната, микрофон в 30–50 см от гитары, аккорд целиком одним ударом. Сложные аккорды (9, 11, 13) и перегруз
        распознаются хуже — смотрите на процент уверенности и варианты «Или».
      </p>
    </div>
  );
}
