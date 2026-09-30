import { useEffect, useState } from 'react';
import { mic } from '../../services/mic';
import type { ChordListener } from './useListener';

/** Настройки микрофона: какой микрофон, усиление (ручное или авто), вычитание шума, строй. */
export function MicSettings({ listener }: { listener: ChordListener }) {
  const { settings, patch, active, gainNow, noiseReady, tuningCents } = listener;
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

  return (
    <>
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
