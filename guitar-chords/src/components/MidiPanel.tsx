import { ALL_DEVICES, type MidiDevice } from '../midi/midiInput';
import { midiName } from '../music/notes';
import { Piano } from './Piano';

export type MidiStatus = 'init' | 'ready' | 'unsupported' | 'denied' | 'unavailable';

interface Props {
  status: MidiStatus;
  error?: string;
  devices: MidiDevice[];
  selected: string;
  onSelect: (id: string) => void;
  active: Set<number>;
  guitarRange: [number, number];
  latch: boolean;
  onLatch: (v: boolean) => void;
  sound: boolean;
  onSound: (v: boolean) => void;
  onKey: (midi: number) => void;
  onClear: () => void;
  onToBoard: () => void;
  onRetry: () => void;
}

export function MidiPanel(p: Props) {
  const notes = [...p.active].sort((a, b) => a - b);
  const outOfRange = notes.filter((n) => n < p.guitarRange[0] || n > p.guitarRange[1]);

  let statusText: string;
  let statusClass = 'warn';
  if (p.status === 'init') statusText = 'Поиск MIDI-устройств…';
  else if (p.status === 'unsupported') statusText = 'Web MIDI недоступен';
  else if (p.status === 'denied') statusText = 'Нет доступа к MIDI';
  else if (p.status === 'unavailable') statusText = 'MIDI-подсистема ОС недоступна';
  else if (p.devices.length === 0) statusText = 'Устройства не найдены — подключите клавиатуру';
  else {
    statusText = `Подключено: ${p.devices.length}`;
    statusClass = 'ok';
  }

  return (
    <section className="panel">
      <h3>
        MIDI-клавиатура
        <span className={`status ${statusClass}`} title={p.error}>
          {statusText}
        </span>
      </h3>

      {(p.status === 'denied' || p.status === 'unavailable') && (
        <div className="row">
          <span className="hint">Клавиатуру можно подключить и после запуска программы.</span>
          <button className="btn" onClick={p.onRetry}>
            ↻ Повторить поиск
          </button>
        </div>
      )}

      {p.devices.length > 0 && (
        <label className="field">
          <span>Устройство</span>
          <select value={p.selected} onChange={(e) => p.onSelect(e.target.value)}>
            <option value={ALL_DEVICES}>Все устройства</option>
            {p.devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.manufacturer ? ` (${d.manufacturer})` : ''}
              </option>
            ))}
          </select>
        </label>
      )}

      <Piano from={36} to={84} active={p.active} guitarRange={p.guitarRange} onKey={p.onKey} />

      <div className="midi-notes">
        {notes.length ? (
          <>
            Ноты: <b>{notes.map(midiName).join(' ')}</b>
            {outOfRange.length > 0 && <span className="hint"> ({outOfRange.map(midiName).join(', ')} — вне диапазона гитары)</span>}
          </>
        ) : (
          <span className="hint">Нажмите клавиши на MIDI-клавиатуре или на экранной клавиатуре</span>
        )}
      </div>

      <label className="check">
        <input type="checkbox" checked={p.latch} onChange={(e) => p.onLatch(e.target.checked)} />
        Фиксировать аккорд после отпускания клавиш
      </label>
      <label className="check">
        <input type="checkbox" checked={p.sound} onChange={(e) => p.onSound(e.target.checked)} />
        Озвучивать ноты с клавиатуры
      </label>

      <div className="row">
        <button className="btn" onClick={p.onToBoard} disabled={notes.length === 0} title="Подобрать аппликатуру на грифе">
          ⇩ На гриф
        </button>
        <button className="btn" onClick={p.onClear} disabled={notes.length === 0}>
          Сбросить ноты
        </button>
      </div>
    </section>
  );
}
