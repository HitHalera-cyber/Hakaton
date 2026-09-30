import { useEffect } from 'react';
import type { ModuleId } from '../modules/ids';
import { getModule } from '../modules/registry';

/** Раздел (модуль) в карточке с заголовком. */
export function ModuleSection({ id, className = '', onClose }: { id: ModuleId; className?: string; onClose?: () => void }) {
  const m = getModule(id);
  return (
    <section className={`panel tools ${className}`}>
      <h2 className="tool-title">
        <span>{m.icon}</span> {m.title}
        {onClose && (
          <button className="btn small close" onClick={onClose} title="Закрыть (Esc)">
            ✕
          </button>
        )}
      </h2>
      <m.View />
    </section>
  );
}

/** Выдвижная панель справа — в раскладках без постоянной области для раздела. */
export function Drawer({ id, onClose }: { id: ModuleId; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        <ModuleSection id={id} onClose={onClose} />
      </aside>
    </>
  );
}
