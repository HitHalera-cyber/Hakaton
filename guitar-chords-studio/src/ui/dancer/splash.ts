// Заставка при запуске: танцор, пока загружается программа. Убирается, когда программа отрисовалась.
import './dancer.css';
import { startDancer } from './dancerCore';

const host = document.getElementById('splash');
if (host) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'dancer-svg');
  svg.setAttribute('viewBox', '0 0 120 86');
  host.prepend(svg);
  const t0 = performance.now();
  // Первые полсекунды — лунная походка, дальше — позы.
  const stop = startDancer(svg, () => ({
    moving: performance.now() - t0 < 1600,
    x: 30 + Math.min(1, (performance.now() - t0) / 1600) * 60,
  }));
  (window as unknown as { __hideSplash?: () => void }).__hideSplash = () => {
    stop();
    host.classList.add('gone');
    window.setTimeout(() => host.remove(), 300);
  };
}
