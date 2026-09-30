import { useEffect, useState } from 'react';
import { MODULES } from '../modules/registry';
import { usePick } from '../store';

/** «О программе»: версия, устройство Studio, горячие клавиши, авторство сэмплов. */
export function AboutDialog() {
  const { open, setOpen } = usePick((s) => ({ open: s.aboutOpen, setOpen: s.setAboutOpen }));
  const [info, setInfo] = useState<AppInfo | null>(null);
  useEffect(() => {
    if (open && window.gc) void window.gc.info().then(setInfo);
  }, [open]);
  if (!open) return null;
  const close = () => setOpen(false);
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>🎸 Гитарные аккорды — Studio</h2>
        <p>Версия {info?.version ?? 'для разработки'}</p>

        <h4>Как устроена Studio</h4>
        <p className="hint">
          Одно хранилище состояния, {MODULES.length} разделов-модулей (меню, поиск и окна строятся по их списку), общий микрофон для всех
          функций, которые слушают гитару, и шина событий между разделами. Новая сборка — вручную: автообновления у Studio нет.
        </p>

        <h4>Горячие клавиши</h4>
        <ul className="keys">
          <li>
            <kbd>Ctrl</kbd> + <kbd>K</kbd> поиск: раздел, песня, аккорд, тема
          </li>
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
          <button className="btn" onClick={close}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
