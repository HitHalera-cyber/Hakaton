import { midiName } from '../../core/music/notes';
import { MAX_CAPO, TUNINGS, TUNING_LIST } from '../../core/music/tunings';
import type { DotLabel } from '../../features/fretboard/Fretboard';
import { useApp } from '../AppContext';

/** Настройки инструмента: строй, каподастр, транспонирование, подписи на грифе. */
export function TopBar() {
  const { settings, guitar } = useApp();
  const { view, patchView } = settings;
  return (
    <>
      <header className="topbar">
        <label className="field inline">
          <span>Строй</span>
          <select value={view.tuning} onChange={(e) => guitar.setTuning(e.target.value)}>
            {[...new Set(TUNING_LIST.map((t) => t.group))].map((g) => (
              <optgroup key={g} label={g}>
                {TUNING_LIST.filter((t) => t.group === g).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="field inline" title="Каподастр зажимает все струны на выбранном ладу">
          <span>Каподастр</span>
          <select value={guitar.capo} onChange={(e) => guitar.setCapo(Number(e.target.value))}>
            <option value={0}>нет</option>
            {Array.from({ length: MAX_CAPO }, (_, i) => i + 1).map((c) => (
              <option key={c} value={c}>
                {c} лад
              </option>
            ))}
          </select>
        </label>
        <div className="transpose" title="Сдвинуть аккорд на полтона (стрелки ← →)">
          <span>Тон</span>
          <button className="btn small" onClick={() => guitar.transpose(-1)}>
            −½
          </button>
          <button className="btn small" onClick={() => guitar.transpose(1)}>
            +½
          </button>
        </div>
        <span className="grow" />
        <button className={`btn toggle ${view.showNotes ? 'on' : ''}`} onClick={() => patchView({ showNotes: !view.showNotes })}>
          Ноты на грифе
        </button>
        <label className="field inline" title="Что писать внутри точек на грифе">
          <span>В точках</span>
          <select value={view.dotLabel} onChange={(e) => patchView({ dotLabel: e.target.value as DotLabel })}>
            <option value="note">ноты</option>
            <option value="degree">ступени</option>
            <option value="finger">пальцы</option>
          </select>
        </label>
      </header>
      {view.tuning === 'custom' && (
        <div className="custom-tuning">
          <span>Свой строй (от басовой струны):</span>
          {view.customStrings.map((m, i) => (
            <select
              key={i}
              value={m}
              onChange={(e) => patchView({ customStrings: view.customStrings.map((x, j) => (j === i ? Number(e.target.value) : x)) })}
            >
              {Array.from({ length: 49 }, (_, k) => 28 + k).map((n) => (
                <option key={n} value={n}>
                  {midiName(n)}
                </option>
              ))}
            </select>
          ))}
          <button className="btn small" onClick={() => patchView({ customStrings: [...TUNINGS.standard.strings] })}>
            Сбросить
          </button>
        </div>
      )}
    </>
  );
}
