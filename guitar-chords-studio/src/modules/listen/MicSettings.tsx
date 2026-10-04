import { useEffect, useState } from 'react';
import { mic } from '../../services/mic';
import { CalibrationWizard } from './CalibrationWizard';
import type { ChordListener } from './useListener';

/** Настройки микрофона: какой микрофон, усиление (ручное или авто), вычитание шума, строй. */
export function MicSettings({ listener }: { listener: ChordListener }) {
  const { settings, patch, active, gainNow, noiseReady, tuningCents, neural } = listener;
  const [devices, setDevices] = useState<{ id: string; label: string }[]>([]);
  const [calibrating, setCalibrating] = useState(false);
  const cal = settings.calibration;

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

  if (calibrating) return <CalibrationWizard onClose={() => setCalibrating(false)} />;

  return (
    <>
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
      <div className="field calib-field">
        <span>Калибровка</span>
        <div className="row">
          <button
            className="btn small"
            onClick={() => setCalibrating(true)}
            title="Сыграть открытые струны по очереди — программа подстроится под гитару и микрофон"
          >
            🎯 {cal ? 'Откалибровать заново' : 'Откалибровать под гитару'}
          </button>
          {cal && (
            <button className="link" onClick={() => patch({ calibration: null })}>
              сбросить
            </button>
          )}
        </div>
        <small className="hint">
          {cal
            ? `Сделана ${new Date(cal.date).toLocaleDateString('ru-RU')}: строй ${cal.tuningCents > 0 ? '+' : ''}${cal.tuningCents} ц, басы ×${Math.max(...cal.gains).toFixed(1)}`
            : 'Не проводилась — займёт полминуты'}
        </small>
      </div>
      {devices.length > 1 && (
        <label className="field">
          <span>Микрофон</span>
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
          Усиление микрофона ×{settings.gain}
          {settings.autoGain && active && ` (сейчас ×${gainNow})`}
        </span>
        <input type="range" min={1} max={12} step={0.5} value={settings.gain} onChange={(e) => patch({ gain: Number(e.target.value) })} />
      </label>
      <label className="check" title="Программа сама прибавляет громкость тихого микрофона и убавляет при перегрузе">
        <input type="checkbox" checked={settings.autoGain} onChange={(e) => patch({ autoGain: e.target.checked })} />
        Автоусиление
      </label>
      <label className="check" title="Гул, вентилятор, шум микрофона запоминаются, пока гитара молчит, и вычитаются из звука">
        <input type="checkbox" checked={settings.denoise} onChange={(e) => patch({ denoise: e.target.checked })} />
        Убирать шум комнаты{settings.denoise && active && (noiseReady ? ' ✓' : ' (помолчите 2 с…)')}
      </label>
      {active && Math.abs(tuningCents) >= 5 && (
        <span className="muted-label" title="Гитара целиком настроена выше или ниже эталона — программа это учитывает">
          Строй гитары: {tuningCents > 0 ? '+' : ''}
          {tuningCents} ц
        </span>
      )}
    </>
  );
}
