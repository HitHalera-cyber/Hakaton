import './dancer.css';
import { useEffect, useRef } from 'react';
import { startDancer } from './dancerCore';

interface Props {
  /** Прогресс 0..1; null — сколько ждать, неизвестно (танцор просто танцует посередине). */
  progress: number | null;
  /** Подпись под полосой. */
  label?: string;
}

/** Экран ожидания: полоса прогресса и танцор на ней. Движется полоса — лунная походка, стоит — позы. */
export function Dancer({ progress, label }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const state = useRef({ progress, changedAt: 0, last: progress });
  if (state.current.last !== progress) {
    state.current.changedAt = performance.now();
    state.current.last = progress;
  }
  state.current.progress = progress;

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const H = 86;
    const resize = () =>
      el.setAttribute('viewBox', `0 0 ${Math.max(60, (el.clientWidth * H) / Math.max(1, el.clientHeight)).toFixed(1)} ${H}`);
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    const stop = startDancer(el, () => {
      const s = state.current;
      const W = el.viewBox.baseVal.width;
      return {
        moving: s.progress != null && performance.now() - s.changedAt < 700,
        x: s.progress == null ? W / 2 : 14 + Math.max(0, Math.min(1, s.progress)) * (W - 28),
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
      <svg ref={svg} className="dancer-svg" />
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
