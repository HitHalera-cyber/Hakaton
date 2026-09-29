import { useRef, type PointerEvent as ReactPointerEvent } from 'react';
import { ToolPanel } from '../panels';
import { DEFAULT_WINDOWS, normalizeWindows, type FreeWindow, type WindowKind } from '../layouts';
import { ALL_TABS, type TabId } from '../navigation';
import { useStored } from '../useStored';
import { BoardCard } from './BoardCard';
import { ChordCard, RailFrame, tabInfo } from './common';

const MIN_W = 260;
const MIN_H = 160;

const windowTitle = (id: WindowKind) => (id === 'chord' ? { icon: '🎸', label: 'Аккорд' } : tabInfo(id));

/**
 * «Свободные окна»: гриф внизу, разделы — в окнах поверх. Окно двигается за заголовок,
 * размер меняется за правый нижний угол; расположение окон сохраняется.
 */
export function FreeLayout() {
  const [stored, setWindows] = useStored<FreeWindow[]>('gc.windows', DEFAULT_WINDOWS);
  const windows = normalizeWindows(stored);
  const desk = useRef<HTMLElement>(null);
  const topZ = () => Math.max(0, ...windows.map((w) => w.z)) + 1;

  const patch = (id: WindowKind, p: Partial<FreeWindow>) =>
    setWindows((list) => normalizeWindows(list).map((w) => (w.id === id ? { ...w, ...p } : w)));
  const focus = (id: WindowKind) => {
    const w = windows.find((x) => x.id === id);
    if (w && w.z !== topZ() - 1) patch(id, { z: topZ() });
  };
  const open = (id: WindowKind) => {
    if (windows.some((w) => w.id === id)) return focus(id);
    const n = windows.length;
    setWindows([...windows, { id, x: 40 + (n % 6) * 36, y: 30 + (n % 6) * 30, w: 440, h: 380, z: topZ() }]);
  };
  const close = (id: WindowKind) => setWindows(windows.filter((w) => w.id !== id));

  /** Перетаскивание окна или его угла: двигаем, пока зажата кнопка мыши. */
  const drag = (e: ReactPointerEvent, win: FreeWindow, mode: 'move' | 'resize') => {
    if (e.button !== 0 || (e.target as HTMLElement).closest('button, select, input')) return;
    e.preventDefault();
    const box = desk.current!.getBoundingClientRect();
    const start = { x: e.clientX, y: e.clientY };
    const z = win.z === topZ() - 1 ? win.z : topZ();
    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - start.x;
      const dy = ev.clientY - start.y;
      if (mode === 'move') {
        patch(win.id, {
          z,
          x: Math.round(Math.min(Math.max(0, win.x + dx), box.width - 80)),
          y: Math.round(Math.min(Math.max(0, win.y + dy), box.height - 40)),
        });
      } else {
        patch(win.id, { z, w: Math.round(Math.max(MIN_W, win.w + dx)), h: Math.round(Math.max(MIN_H, win.h + dy)) });
      }
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.classList.remove('dragging');
    };
    document.body.classList.add('dragging');
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const closed: { id: WindowKind; label: string }[] = [{ id: 'chord' as WindowKind, label: 'Аккорд' }, ...ALL_TABS]
    .filter((t) => !windows.some((w) => w.id === t.id))
    .map((t) => ({ id: t.id, label: t.label }));

  return (
    <RailFrame active={null} onNav={(tab: TabId) => open(tab)}>
      <main className="desktop" ref={desk}>
        <div className="desk-tools">
          <select
            className="add-window"
            value=""
            onChange={(e) => e.target.value && open(e.target.value as WindowKind)}
            title="Открыть раздел в новом окне"
          >
            <option value="">+ Окно…</option>
            {closed.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
          <button className="btn small" onClick={() => setWindows(DEFAULT_WINDOWS)} title="Вернуть окна на места по умолчанию">
            ↺ Окна
          </button>
        </div>
        <div className="desk-board">
          <BoardCard />
        </div>
        {windows.map((w) => {
          const t = windowTitle(w.id);
          return (
            <section
              key={w.id}
              className="panel free-win"
              style={{ left: w.x, top: w.y, width: w.w, height: w.h, zIndex: 10 + w.z }}
              onPointerDown={() => focus(w.id)}
            >
              <header className="free-win-head" onPointerDown={(e) => drag(e, w, 'move')}>
                <span>{t.icon}</span>
                <b>{t.label}</b>
                <span className="grow" />
                <button className="btn small close" onClick={() => close(w.id)} title="Закрыть окно">
                  ✕
                </button>
              </header>
              <div className="free-win-body">{w.id === 'chord' ? <ChordCard /> : <ToolPanel tab={w.id} />}</div>
              <div className="free-win-resize" onPointerDown={(e) => drag(e, w, 'resize')} title="Потяните, чтобы изменить размер" />
            </section>
          );
        })}
      </main>
    </RailFrame>
  );
}
