import { useEffect, useState } from 'react';

/** Состояние обновлений и сведения о версии (из главного процесса Electron). */
export function useUpdates() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  useEffect(() => {
    if (!window.gc) return;
    void window.gc.info().then(setInfo);
    return window.gc.onUpdate(setStatus);
  }, []);
  return { info, status };
}

/** Полоса вверху окна: «Доступна новая версия». */
export function UpdateBanner({ status }: { status: UpdateStatus | null }) {
  const [hidden, setHidden] = useState(false);
  if (!status || hidden || !['available', 'downloading', 'downloaded'].includes(status.state)) return null;
  return (
    <div className="update-banner">
      {status.state === 'available' && (
        <>
          <span>🎉 Доступна новая версия {status.version}</span>
          <button className="btn small primary" onClick={() => window.gc?.downloadUpdate()}>
            Скачать и установить
          </button>
        </>
      )}
      {status.state === 'downloading' && <span>Загрузка обновления… {status.percent ?? 0}%</span>}
      {status.state === 'downloaded' && (
        <>
          <span>Версия {status.version} загружена</span>
          <button className="btn small primary" onClick={() => window.gc?.installUpdate()}>
            Перезапустить и обновить
          </button>
        </>
      )}
      <button className="icon" onClick={() => setHidden(true)} title="Скрыть">
        ✕
      </button>
    </div>
  );
}

const STATUS_TEXT: Record<UpdateStatus['state'], string> = {
  checking: 'Проверяю обновления…',
  available: 'Доступна новая версия',
  none: 'У вас последняя версия ✓',
  downloading: 'Загрузка обновления…',
  downloaded: 'Обновление загружено — перезапустите программу',
  error: 'Не удалось проверить обновления',
  unsupported: 'Автообновление недоступно в этой версии',
};

export function AboutDialog({ info, status, onClose }: { info: AppInfo | null; status: UpdateStatus | null; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>🎸 Гитарные аккорды</h2>
        <p>Версия {info?.version ?? 'для разработки'}</p>

        <h4>Обновления</h4>
        {!window.gc ? (
          <p className="hint">Обновления доступны только в установленной программе.</p>
        ) : info?.portable || !info?.updatesSupported ? (
          <p className="hint">
            {info?.portable ? 'Portable-версия не обновляется сама. ' : ''}Новые версии можно скачать на странице релизов.
          </p>
        ) : (
          <p>
            {status ? STATUS_TEXT[status.state] : 'Программа проверяет обновления при запуске.'}
            {status?.version ? ` (${status.version})` : ''}
            {status?.state === 'error' && status.message ? <span className="hint"> — {status.message}</span> : null}
          </p>
        )}
        <div className="row">
          {info?.updatesSupported && (
            <button className="btn primary" onClick={() => window.gc?.checkUpdates()}>
              Проверить обновления
            </button>
          )}
          {window.gc && (
            <button className="btn" onClick={() => window.gc?.openReleases()}>
              Страница релизов
            </button>
          )}
        </div>

        <h4>Горячие клавиши</h4>
        <ul className="keys">
          <li>
            <kbd>Пробел</kbd> сыграть аккорд
          </li>
          <li>
            <kbd>Esc</kbd> остановить звук
          </li>
          <li>
            <kbd>Delete</kbd> очистить гриф
          </li>
          <li>
            <kbd>←</kbd> <kbd>→</kbd> транспонировать на полтона
          </li>
        </ul>

        <h4>Звук</h4>
        <p className="hint">
          Сэмплы гитар: FluidR3 GM SoundFont (Frank Wen), лицензия Creative Commons Attribution 3.0, в конвертации проекта
          midi-js-soundfonts (Benjamin Gleitzman).
        </p>
        <div className="row">
          <span className="grow" />
          <button className="btn" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
