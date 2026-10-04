// Заставка при запуске: танцор, пока загружается программа. Убирается, когда программа отрисовалась.
import './dancer.css';
import { DANCER_STYLE, fitCanvas, startPixelDancer } from './pixelDancer';

const host = document.getElementById('splash');
if (host) {
  const canvas = document.createElement('canvas');
  canvas.className = 'dancer-canvas';
  host.prepend(canvas);
  fitCanvas(canvas);
  const t0 = performance.now();
  // Первые полсекунды — лунная походка, дальше — позы.
  const stop = startPixelDancer(canvas, DANCER_STYLE, () => ({
    moving: performance.now() - t0 < 1600,
    x: canvas.width * (0.25 + Math.min(1, (performance.now() - t0) / 1600) * 0.5),
  }));
  (window as unknown as { __hideSplash?: () => void }).__hideSplash = () => {
    stop();
    host.classList.add('gone');
    window.setTimeout(() => host.remove(), 300);
  };
}
