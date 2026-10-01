import {
  FUNCTION_RU,
  MAJOR_LABELS,
  circlePosition,
  guessKey,
  keyName,
  romanInKey,
  type CircleKey,
  type CirclePos,
} from '../../core/music/circle';
import { CircleOfFifths } from '../../ui/CircleOfFifths';

export interface CircleChord {
  rootPc: number;
  templateId: string;
  symbol: string;
  nameRu: string;
  source: 'guitar' | 'board' | 'midi' | 'song';
  /** Уникальный номер события — для «вспышки». */
  id: number;
}

interface Props {
  trail: CircleChord[];
  keyChoice: string;
  onKeyChoice: (v: string) => void;
  /** Идёт ли прослушивание гитары. */
  listening: boolean;
  onPick: (pos: CirclePos) => void;
  onClear: () => void;
}

const SOURCE_RU: Record<CircleChord['source'], string> = {
  guitar: '🎤 с гитары',
  board: 'с грифа',
  midi: '🎹 с MIDI',
  song: '🎧 из песни',
};

/** Тональность: выбранная вручную или угаданная по последним аккордам. */
export function resolveKey(keyChoice: string, trail: CircleChord[]): { key: CircleKey | null; auto: boolean } {
  if (keyChoice !== 'auto') {
    const [i, mode] = keyChoice.split('-');
    return { key: { index: Number(i), mode: mode as CircleKey['mode'] }, auto: false };
  }
  return { key: guessKey(trail.slice(0, 8).map((c) => circlePosition(c.rootPc, c.templateId))), auto: true };
}

export function CirclePanel({ trail, keyChoice, onKeyChoice, listening, onPick, onClear }: Props) {
  const current = trail[0] ?? null;
  const active = current ? circlePosition(current.rootPc, current.templateId) : null;
  const { key, auto } = resolveKey(keyChoice, trail);
  const roman = active && key ? romanInKey(active, key) : null;

  return (
    <div className="tab-body circle-tab">
      <div className="row">
        {listening ? (
          <span className="listening-note" title="Аккорды с гитары подсвечиваются на круге">
            ● слушаю гитару
          </span>
        ) : (
          <span className="hint">Аккорды с гитары подсвечиваются, когда включено «Слушать аккорд»</span>
        )}
        <label className="field inline">
          <span>Тональность</span>
          <select value={keyChoice} onChange={(e) => onKeyChoice(e.target.value)}>
            <option value="auto">угадывать по аккордам</option>
            <optgroup label="Мажор">
              {MAJOR_LABELS.map((_, i) => (
                <option key={`M${i}`} value={`${i}-major`}>
                  {keyName({ index: i, mode: 'major' })}
                </option>
              ))}
            </optgroup>
            <optgroup label="Минор">
              {MAJOR_LABELS.map((_, i) => (
                <option key={`m${i}`} value={`${i}-minor`}>
                  {keyName({ index: i, mode: 'minor' })}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
      </div>

      <div className="circle-wrap">
        <CircleOfFifths
          active={active}
          pulseKey={current?.id}
          trail={trail.slice(1, 4).map((c) => circlePosition(c.rootPc, c.templateId))}
          keySel={key}
          center={current ? { title: current.symbol, subtitle: roman ?? undefined } : { title: '—', subtitle: 'сыграйте аккорд' }}
          onPick={onPick}
          size={380}
        />
        <div className="circle-info">
          {current ? (
            <>
              <div className="ci-symbol">{current.symbol}</div>
              <div>{current.nameRu}</div>
              <div className="hint">{SOURCE_RU[current.source]}</div>
            </>
          ) : (
            <div className="hint">
              Нажмите «Слушать аккорд» и играйте — аккорд засветится на круге. Можно и ставить точки на грифе, играть на MIDI-клавиатуре или
              включить песню на вкладке «Разбор песни».
            </div>
          )}
          {key && (
            <div className="ci-key">
              Тональность: <b>{keyName(key)}</b>
              {auto && <span className="hint"> (угадана по аккордам)</span>}
            </div>
          )}
          {current && key && (
            <div className="ci-func">
              {roman ? (
                <>
                  Ступень: <b>{roman}</b> — {FUNCTION_RU[roman] ?? ''}
                </>
              ) : (
                <>Аккорд не из этой тональности (заимствованный или модуляция)</>
              )}
            </div>
          )}
          {trail.length > 1 && (
            <div className="ci-trail">
              <span className="muted-label">Последние:</span>
              {trail.slice(0, 8).map((c, i) => (
                <span key={c.id} className={`alt ${i === 0 ? 'now' : ''}`}>
                  {c.symbol}
                </span>
              ))}
              <button className="link" onClick={onClear}>
                очистить
              </button>
            </div>
          )}
          <details className="ci-help">
            <summary>Как читать круг</summary>
            <p>
              По часовой стрелке каждый аккорд — на квинту выше предыдущего (C → G → D…), против часовой — на кварту (C → F → Bb…). Снаружи
              — мажорные аккорды, в середине — параллельные минорные, внутри — уменьшённые.
            </p>
            <p>
              Подсвеченный сектор — аккорды выбранной тональности: тоника и два соседа (субдоминанта слева, доминанта справа), под ними —
              минорные ступени и уменьшённый аккорд. Чем ближе аккорды на круге, тем мягче переход между ними. Клик по ячейке — поставить
              аккорд на гриф и сыграть.
            </p>
          </details>
        </div>
      </div>
    </div>
  );
}
