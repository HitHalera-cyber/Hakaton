import { useEffect } from 'react';
import { createPortal } from 'react-dom';

/** Короткая справка у курсора (правый клик по пункту меню). Закрывается кликом мимо или Esc. */
export function HelpPopover({
  x,
  y,
  icon,
  title,
  text,
  onClose,
}: {
  x: number;
  y: number;
  icon: string;
  title: string;
  text: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const close = () => onClose();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('pointerdown', close);
    window.addEventListener('keydown', onKey);
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('pointerdown', close);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', close);
    };
  }, [onClose]);
  const w = 340;
  const left = Math.max(8, Math.min(x + 12, window.innerWidth - w - 8));
  const top = Math.max(8, Math.min(y - 10, window.innerHeight - 200));
  return createPortal(
    <div className="help-pop" style={{ left, top, width: w }} role="tooltip" onPointerDown={(e) => e.stopPropagation()}>
      <b>
        {icon} {title}
      </b>
      <p>{text}</p>
      <small>Клик левой кнопкой — открыть раздел</small>
    </div>,
    document.body,
  );
}
