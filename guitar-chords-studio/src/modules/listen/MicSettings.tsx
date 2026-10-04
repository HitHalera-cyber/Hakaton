import { useEffect, useState } from 'react';
import { mic } from '../../services/mic';
import { Dancer } from '../../ui/dancer/Dancer';
import type { ChordListener } from './useListener';

/** Настройки микрофона: какой микрофон, усиление (ручное или авто), вычитание шума, строй. */
export function MicSettings({ listener }: { listener: ChordListener }) {
  const { settings, patch, active, gainNow, noiseReady, tuningCents, neural } = listener;
  const [devices, setDevices] = useState<{ id: string; label: string }[]>([]);

  // Названия микрофонов доступны только после разрешения — перечитываем, когда слушание включилось.
  useEffect(() => {
    let alive = true;
    mic
      .devices()
      .then((d) => alive && setDevices(d))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [active]);

  const line = settings.input === 'line';
  return (
    <>
      <div className="field input-field">
        <span>Откуда звук</span>
        <div className="segmented" role="radiogroup" aria-label="Источник звука">
          <button
            className={!line ? 'on' : ''}
            onClick={() => patch({ input: 'mic', channel: 'mix', autoGain: true, denoise: true, gain: 3 })}
            title="Микрофон ноутбука, веб-камеры или USB-микрофон: гитара играет в комнате"
          >
            🎤 Микрофон
          </button>
          <button
            className={line ? 'on' : ''}
            onClick={() => patch({ input: 'line', autoGain: false, denoise: false, gain: 1 })}
            title="Гитара по кабелю: через звуковую карту, гитарный USB-кабель, комбик с USB или выход комбика в линейный вход"
          >
            🎸 Кабель
          </button>
        </div>
        {line && (
          <small className="hint">
            Подключите гитару через звуковую карту (Focusrite, Behringer UMC и т. п.), гитарный USB-кабель или комбик с USB, либо выход
            комбика «Line out / Phones» — в линейный вход компьютера (не в микрофонный!). Выберите это устройство ниже. На комбике — чистый
            канал без перегруза и эффектов: так ноты слышны точнее. Если индикатор громкости не двигается — выберите другой канал.
          </small>
        )}
      </div>
      {line && (
        <label className="field">
          <span>Канал</span>
          <select value={settings.channel} onChange={(e) => patch({ channel: e.target.value as 'mix' | 'left' | 'right' })}>
            <option value="mix">Оба (сводить)</option>
            <option value="left">Левый — вход 1</option>
            <option value="right">Правый — вход 2</option>
          </select>
        </label>
      )}
      <div className="field engine-field">
        <span>Чем распознавать</span>
        <div className="segmented" role="radiogroup" aria-label="Движок распознавания">
          <button
            className={settings.engine === 'dsp' ? 'on' : ''}
            onClick={() => patch({ engine: 'dsp' })}
            title="Анализ спектра звука: мгновенно, работает на любом компьютере"
          >
            Формулы
          </button>
          <button
            className={settings.engine === 'neural' ? 'on' : ''}
            onClick={() => patch({ engine: 'neural' })}
            title="Нейросеть Basic Pitch: точнее слышит ноты и октавы, отвечает через ~1 с, нужна видеокарта (или терпение)"
          >
            Нейросеть (бета)
          </button>
        </div>
        {settings.engine === 'neural' && neural === 'loading' && <Dancer progress={null} label="Загружаю нейросеть…" />}
        {settings.engine === 'neural' && (
          <small className="hint">
            {neural === 'loading'
              ? 'Загружаю нейросеть…'
              : neural === 'busy'
                ? 'Нейросеть слушает…'
                : neural === 'error'
                  ? 'Нейросеть не загрузилась — работают формулы'
                  : neural === 'ready'
                    ? `Нейросеть готова (${listener.neuralBackend || '…'}${listener.neuralMs ? `, ответ за ${listener.neuralMs} мс` : ''})${listener.neuralMs > 900 ? ' — медленно, лучше «Формулы»' : ''}`
                    : 'Загрузится при «Начать слушать»'}
          </small>
        )}
      </div>
      {(devices.length > 1 || line) && (
        <label className="field">
          <span>{line ? 'Устройство (звуковая карта)' : 'Микрофон'}</span>
          <select value={settings.deviceId} onChange={(e) => patch({ deviceId: e.target.value })}>
            <option value="">Системный по умолчанию</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="slider">
        <span>
          {line ? 'Усиление входа' : 'Усиление микрофона'} ×{settings.gain}
          {settings.autoGain && active && ` (сейчас ×${gainNow})`}
        </span>
        <input
          type="range"
          min={line ? 0.25 : 1}
          max={12}
          step={0.25}
          value={settings.gain}
          onChange={(e) => patch({ gain: Number(e.target.value) })}
        />
      </label>
      <label className="check" title="Программа сама прибавляет громкость тихого микрофона и убавляет при перегрузе">
        <input type="checkbox" checked={settings.autoGain} onChange={(e) => patch({ autoGain: e.target.checked })} />
        Автоусиление
      </label>
      <label
        className="check"
        title="Шумодав: гул и шум микрофона запоминаются, пока гитара молчит, и вычитаются; речь, хлопки, стук и свист не принимаются за аккорды"
      >
        <input type="checkbox" checked={settings.denoise} onChange={(e) => patch({ denoise: e.target.checked })} />
        Шумодав (шум и посторонние звуки){settings.denoise && active && (noiseReady ? ' ✓' : ' (помолчите 2 с…)')}
      </label>
      {active && settings.denoise && Date.now() - listener.ignoredAt < 2500 && (
        <span className="muted-label" title="Звук не похож на гитару — аккорд не показан">
          🔇 Посторонний звук пропущен
        </span>
      )}
      {active && Math.abs(tuningCents) >= 5 && (
        <span className="muted-label" title="Гитара целиком настроена выше или ниже эталона — программа это учитывает">
          Строй гитары: {tuningCents > 0 ? '+' : ''}
          {tuningCents} ц
        </span>
      )}
    </>
  );
}
