import './dancer.css';
import { useEffect, useRef } from 'react';
import { DANCER_STYLE, fitCanvas, startPixelDancer } from './pixelDancer';

interface Props {
  /** Прогресс 0..1; null — сколько ждать, неизвестно (танцор просто танцует посередине). */
  progress: number | null;
  /** Подпись под полосой. */
  label?: string;
}

/** Экран ожидания: полоса прогресса и танцор на ней. Движется полоса — лунная походка, стоит — позы. */
export function Dancer({ progress, label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef({ progress, changedAt: 0, last: progress });
  if (state.current.last !== progress) {
    state.current.changedAt = performance.now();
    state.current.last = progress;
  }
  state.current.progress = progress;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    fitCanvas(el);
    const ro = new ResizeObserver(() => fitCanvas(el));
    ro.observe(el);
    const stop = startPixelDancer(el, DANCER_STYLE, () => {
      const s = state.current;
      const W = el.width;
      const pad = el.height * 0.3;
      return {
        moving: s.progress != null && performance.now() - s.changedAt < 700,
        x: s.progress == null ? W / 2 : pad + Math.max(0, Math.min(1, s.progress)) * (W - 2 * pad),
      };
    });
    return () => {
      stop();
      ro.disconnect();
    };
  }, []);

  return (
    <div
      className="dancer"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={progress == null ? undefined : Math.round(progress * 100)}
    >
      <canvas ref={canvas} className="dancer-canvas" />
      <div className="dancer-track">
        <span
          style={{ width: progress == null ? '100%' : `${Math.round(progress * 100)}%` }}
          className={progress == null ? 'indeterminate' : ''}
        />
      </div>
      {label && <small className="dancer-label">{label}</small>}
    </div>
  );
}
