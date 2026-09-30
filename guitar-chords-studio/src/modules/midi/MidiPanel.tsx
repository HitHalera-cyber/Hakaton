import './midi.css';
import { ALL_DEVICES, type MidiDevice } from '../../core/midi/midiInput';
import { midiName } from '../../core/music/notes';
import { Piano } from '../../ui/Piano';

export type MidiStatus = 'init' | 'ready' | 'unsupported' | 'denied' | 'unavailable';

interface Props {
  status: MidiStatus;
  error?: string;
  devices: MidiDevice[];
  outputs: MidiDevice[];
  selected: string;
  onSelect: (id: string) => void;
  output: string;
  onOutput: (id: string) => void;
  muteInternal: boolean;
  onMuteInternal: (v: boolean) => void;
  active: Set<number>;
  range: [number, number];
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
  const outOfRange = notes.filter((n) => n < p.range[0] || n > p.range[1]);

  let statusText: string;
  let statusClass = 'warn';
  if (p.status === 'init') statusText = 'Поиск MIDI-устройств…';
  else if (p.status === 'unsupported') statusText = 'Web MIDI недоступен';
  else if (p.status === 'denied') statusText = 'Нет доступа к MIDI';
  else if (p.status === 'unavailable') statusText = 'MIDI-подсистема ОС недоступна';
  else if (p.devices.length === 0) statusText = 'Клавиатура не найдена — подключите по USB';
  else {
    statusText = `Подключено: ${p.devices.length}`;
    statusClass = 'ok';
  }

  return (
    <div className="tab-body">
      <div className="row between">
        <span className={`status ${statusClass}`} title={p.error}>
          {statusText}
        </span>
        {(p.status === 'denied' || p.status === 'unavailable' || p.devices.length === 0) && p.status !== 'init' && (
          <button className="btn small" onClick={p.onRetry}>
            ↻ Повторить поиск
          </button>
        )}
      </div>

      <div className="grid2">
        <label className="field">
          <span>Вход (клавиатура)</span>
          <select value={p.selected} onChange={(e) => p.onSelect(e.target.value)} disabled={p.devices.length === 0}>
            <option value={ALL_DEVICES}>Все устройства</option>
            {p.devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.manufacturer ? ` (${d.manufacturer})` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Выход (в DAW / синтезатор)</span>
          <select value={p.output} onChange={(e) => p.onOutput(e.target.value)}>
            <option value="">Не выводить</option>
            {p.outputs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {p.output && (
        <label className="check">
          <input type="checkbox" checked={p.muteInternal} onChange={(e) => p.onMuteInternal(e.target.checked)} />
          Только MIDI-выход (выключить встроенный звук)
        </label>
      )}

      <Piano from={36} to={84} active={p.active} range={p.range} onKey={p.onKey} />

      <div className="midi-notes">
        {notes.length ? (
          <>
            Ноты: <b>{notes.map(midiName).join(' ')}</b>
            {outOfRange.length > 0 && <span className="hint"> ({outOfRange.map(midiName).join(', ')} — вне диапазона инструмента)</span>}
          </>
        ) : (
          <span className="hint">Нажмите клавиши на MIDI-клавиатуре или мышью на экранной клавиатуре</span>
        )}
      </div>

      <label className="check">
        <input type="checkbox" checked={p.latch} onChange={(e) => p.onLatch(e.target.checked)} />
        Держать аккорд после отпускания клавиш
      </label>
      <label className="check">
        <input type="checkbox" checked={p.sound} onChange={(e) => p.onSound(e.target.checked)} />
        Озвучивать нажатые клавиши
      </label>

      <div className="row">
        <button className="btn" onClick={p.onToBoard} disabled={notes.length === 0} title="Подобрать аппликатуру на грифе">
          ⇩ Перенести на гриф
        </button>
        <button className="btn" onClick={p.onClear} disabled={notes.length === 0}>
          Сбросить ноты
        </button>
      </div>
      <p className="hint">
        Чтобы отправлять аккорды в FL Studio, Ableton и др. на Windows, создайте виртуальный порт в бесплатной программе loopMIDI и выберите
        его в «Выход».
      </p>
    </div>
  );
}
