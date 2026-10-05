import { useEffect, useRef } from 'react';
import { recorder, timelineLength, type Take } from '../../services/recorder';

/** Пики громкости по столбцам: [мин, макс] для каждого из n столбцов. */
function peaks(data: Float32Array, n: number, from: number, perCol: number): Float32Array {
  const out = new Float32Array(n * 2);
  for (let c = 0; c < n; c++) {
    let lo = 0;
    let hi = 0;
    const a = Math.floor(from + c * perCol);
    const b = Math.floor(from + (c + 1) * perCol);
    for (let i = Math.max(0, a); i < Math.min(data.length, b); i++) {
      const x = data[i];
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
    out[c * 2] = lo;
    out[c * 2 + 1] = hi;
  }
  return out;
}

/**
 * Две дорожки на одной шкале времени: сверху оригинал, снизу дубль (сдвинут туда, где он начался
 * на оригинале). Бегунок показывает, что играет; щелчок — играть с этого места.
 */
export function Waveform({ take, height = 150 }: { take: Take | null; height?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const ref = recorder.state.reference;
  const total = Math.max(0.5, timelineLength(take));

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    let raf = 0;
    const css = getComputedStyle(el);
    const accent = css.getPropertyValue('--accent').trim() || '#c33';
    const text2 = css.getPropertyValue('--text-2').trim() || '#999';
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const W = Math.max(1, Math.round(el.clientWidth * dpr));
      const H = Math.max(1, Math.round(height * dpr));
      if (el.width !== W || el.height !== H) {
        el.width = W;
        el.height = H;
      }
      const ctx = el.getContext('2d')!;
      ctx.clearRect(0, 0, W, H);
      const lanes = ref && take?.refAt != null ? 2 : 1;
      const laneH = H / lanes;
      const lane = (data: Float32Array, rate: number, start: number, row: number, color: string, label: string) => {
        // start — где на шкале начинается дорожка (с).
        const x0 = (start / total) * W;
        const w = (data.length / rate / total) * W;
        const cols = Math.max(1, Math.floor(w));
        const pk = peaks(data, cols, 0, data.length / cols);
        const mid = laneH * row + laneH / 2;
        ctx.fillStyle = color;
        for (let c = 0; c < cols; c++) {
          const lo = pk[c * 2];
          const hi = pk[c * 2 + 1];
          ctx.fillRect(x0 + c, mid - hi * laneH * 0.45, 1, Math.max(1, (hi - lo) * laneH * 0.45));
        }
        ctx.fillStyle = text2;
        ctx.font = `${11 * dpr}px sans-serif`;
        ctx.fillText(label, 6 * dpr, laneH * row + 14 * dpr);
      };
      if (ref && (lanes === 2 || !take)) lane(ref.buffer.getChannelData(0), ref.buffer.sampleRate, 0, 0, text2, 'Оригинал');
      if (take) lane(take.samples, take.sampleRate, lanes === 2 ? (take.refAt ?? 0) : 0, lanes - 1, accent, take.name);
      const pos = recorder.position();
      if (pos != null) {
        ctx.fillStyle = accent;
        ctx.fillRect((pos / total) * W, 0, 2 * dpr, H);
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [take, ref, total, height]);

  return (
    <canvas
      ref={canvas}
      className="rec-wave"
      style={{ height }}
      title="Щёлкните — играть с этого места"
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        recorder.play(take?.id ?? null, ((e.clientX - r.left) / r.width) * total);
      }}
    />
  );
}
