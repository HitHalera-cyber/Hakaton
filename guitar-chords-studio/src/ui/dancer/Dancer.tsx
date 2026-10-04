import './dancer.css';
import { useEffect, useRef } from 'react';
import { DANCER_STYLE, fitCanvas, startPixelDancer } from './pixelDancer';

interface Props {
  /** Прогресс 0..1; null — сколько ждать, неизвестно (танцор просто танцует посередине). */
  progress: number | null;
  /** Подпись под полосой. */
  label?: string;
}

/** Как быстро показанная полоса догоняет настоящий прогресс: постоянная времени, с, и наибольшая скорость (доля в секунду). */
const EASE_SECONDS = 1.4;
const MAX_SPEED = 0.18;

/**
 * Экран ожидания: полоса прогресса и танцор на её конце. Полоса не прыгает, а плавно догоняет
 * настоящий прогресс — танцор идёт за ней лунной походкой; когда догнал — танцует на месте.
 */
export function Dancer({ progress, label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const target = useRef(progress);
  target.current = progress;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    fitCanvas(el);
    const ro = new ResizeObserver(() => fitCanvas(el));
    ro.observe(el);
    let shown = 0;
    let last = performance.now();
    const stop = startPixelDancer(el, DANCER_STYLE, () => {
      const now = performance.now();
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const goal = target.current;
      const W = el.width;
      if (goal == null) return { moving: false, x: W / 2 };
      // Новый запуск (прогресс сбросился) — полосу тоже сначала.
      if (goal < shown - 0.25) shown = goal;
      const prev = shown;
      const step = (goal - shown) * (1 - Math.exp(-dt / EASE_SECONDS));
      shown += Math.max(-MAX_SPEED * dt, Math.min(MAX_SPEED * dt, step));
      if (bar.current) bar.current.style.width = `${(shown * 100).toFixed(2)}%`;
      const pad = el.height * 0.35;
      return { moving: shown - prev > 0.0004, x: Math.max(pad, Math.min(W - pad, shown * W)) };
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
        <span ref={bar} style={progress == null ? { width: '100%' } : undefined} className={progress == null ? 'indeterminate' : ''} />
      </div>
      {label && <small className="dancer-label">{label}</small>}
    </div>
  );
}
