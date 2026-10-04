// Пиксельный танцор: тот же скелет и те же движения, но фигура растеризуется в крупные пиксели
// с ограниченной палитрой (как в старых играх) — белые носки, одна белая перчатка, шляпа.

import { DancerAnimator, skeleton, type Pose } from './dancerCore';

export interface PixelStyle {
  id: string;
  name: string;
  /** Высота фигуры в «пикселях» (чем меньше — тем крупнее пиксель). */
  height: number;
  colors: {
    suit: string;
    suitBack: string;
    skin: string;
    hat: string;
    band: string;
    glove: string;
    socks: string;
    shoes: string;
    outline?: string;
  };
  /** Свечение вокруг фигуры (неон). */
  glow?: string;
}

type Ink = keyof PixelStyle['colors'];
const INKS: Ink[] = ['suit', 'suitBack', 'skin', 'hat', 'band', 'glove', 'socks', 'shoes', 'outline'];

/** Растр W×H, в каждой клетке — номер «краски» (0 — пусто). */
class Raster {
  data: Uint8Array;
  constructor(
    public w: number,
    public h: number,
  ) {
    this.data = new Uint8Array(w * h);
  }
  dot(x: number, y: number, r: number, ink: number) {
    const x0 = Math.floor(x - r);
    const x1 = Math.ceil(x + r);
    const y0 = Math.floor(y - r);
    const y1 = Math.ceil(y + r);
    for (let yy = y0; yy <= y1; yy++)
      for (let xx = x0; xx <= x1; xx++) {
        if (xx < 0 || yy < 0 || xx >= this.w || yy >= this.h) continue;
        if ((xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2 <= r * r) this.data[yy * this.w + xx] = ink;
      }
  }
  line(a: [number, number], b: [number, number], r: number, ink: number, from = 0, to = 1) {
    const n = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) * 2));
    for (let i = 0; i <= n; i++) {
      const t = from + ((to - from) * i) / n;
      this.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, r, ink);
    }
  }
  outline(ink: number) {
    const src = this.data.slice();
    for (let y = 0; y < this.h; y++)
      for (let x = 0; x < this.w; x++) {
        if (src[y * this.w + x]) continue;
        const near = [
          [1, 0],
          [-1, 0],
          [0, 1],
          [0, -1],
        ].some(([dx, dy]) => {
          const xx = x + dx;
          const yy = y + dy;
          return xx >= 0 && yy >= 0 && xx < this.w && yy < this.h && src[yy * this.w + xx] && src[yy * this.w + xx] !== ink;
        });
        if (near) this.data[y * this.w + x] = ink;
      }
  }
}

/** Нарисовать позу в растр: x — центр по горизонтали, низ фигуры — у нижнего края. */
export function rasterize(pose: Pose, scaleX: number, w: number, h: number, style: PixelStyle, x = w / 2): Raster {
  const R = new Raster(w, h);
  const k = style.height / 78; // высота скелета ~78 единиц
  const sk = skeleton(pose);
  const feet = [...sk.legF, ...sk.legB].map((q) => q[1]);
  const floor = Math.max(...feet);
  const sx = Math.abs(scaleX) < 0.12 ? 0.12 * Math.sign(scaleX || 1) : scaleX;
  const T = (q: [number, number]): [number, number] => [x + q[0] * k * sx, h - 1 - (floor - q[1]) * k];
  const ink = (n: Ink) => INKS.indexOf(n) + 1;
  const limb = Math.max(0.75, 1.5 * k);
  const leg = (l: [number, number][], back: boolean) => {
    const [hip, knee, ankle, toe] = l.map(T);
    R.line(hip, knee, limb * 1.15, ink(back ? 'suitBack' : 'suit'));
    R.line(knee, ankle, limb * 1.1, ink(back ? 'suitBack' : 'suit'), 0, 0.72);
    R.line(knee, ankle, limb * 0.95, ink('socks'), 0.72, 1);
    R.line(ankle, toe, limb * 1.05, ink('shoes'));
  };
  const arm = (a: [number, number][], back: boolean, gloved: boolean) => {
    const [sh, el, hand] = a.map(T);
    R.line(sh, el, limb, ink(back ? 'suitBack' : 'suit'));
    R.line(el, hand, limb * 0.95, ink(back ? 'suitBack' : 'suit'), 0, 0.72);
    R.line(el, hand, limb * 1.15, ink(gloved ? 'glove' : 'skin'), 0.72, 1);
  };
  leg(sk.legB, true);
  arm(sk.armB, true, false);
  R.line(T(sk.hip), T(sk.neck), limb * 1.9, ink('suit'));
  leg(sk.legF, false);
  arm(sk.armF, false, true);
  const head = T(sk.head);
  R.dot(head[0], head[1], 5.4 * k, ink('skin'));
  // Федора: поля, тулья и лента.
  const tilt = ((pose.hat - pose.lean * 0.6) * Math.PI) / 180;
  const rot = (dx: number, dy: number): [number, number] => [
    head[0] + (dx * Math.cos(tilt) - dy * Math.sin(tilt)) * k * sx,
    head[1] + (dx * Math.sin(tilt) + dy * Math.cos(tilt)) * k,
  ];
  R.line(rot(-8.5, -3.8), rot(8.5, -4.4), Math.max(0.6, 1.1 * k), ink('hat'));
  for (let dy = -10.5; dy <= -4; dy += 0.8) R.line(rot(-4.4, dy), rot(4.4, dy), Math.max(0.5, 0.8 * k), ink('hat'));
  R.line(rot(-4.4, -5.6), rot(4.4, -5.6), Math.max(0.5, 0.7 * k), ink('band'));
  if (style.colors.outline) R.outline(ink('outline'));
  return R;
}

/** Нарисовать растр на холсте: каждый «пиксель» — квадрат px×px. */
export function paint(ctx: CanvasRenderingContext2D, R: Raster, style: PixelStyle, px: number, ox = 0, oy = 0) {
  const pal = INKS.map((n) => style.colors[n] ?? 'transparent');
  if (style.glow) {
    ctx.shadowColor = style.glow;
    ctx.shadowBlur = px * 3;
  }
  for (let y = 0; y < R.h; y++)
    for (let x = 0; x < R.w; x++) {
      const v = R.data[y * R.w + x];
      if (!v) continue;
      ctx.fillStyle = pal[v - 1];
      ctx.fillRect(ox + x * px, oy + y * px, px, px);
    }
  ctx.shadowBlur = 0;
}

/** Запустить пиксельного танцора на холсте. */
export function startPixelDancer(
  canvas: HTMLCanvasElement,
  style: PixelStyle,
  getState: () => { moving: boolean; x?: number },
): () => void {
  const anim = new DancerAnimator();
  let last = performance.now();
  let raf = 0;
  const frame = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const st = getState();
    const { pose, scaleX } = anim.step(dt, st.moving);
    const ctx = canvas.getContext('2d')!;
    const px = Math.max(2, Math.floor(canvas.height / (style.height + 6)));
    const w = Math.floor(canvas.width / px);
    const h = Math.floor(canvas.height / px);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const x = st.x != null ? (st.x * w) / canvas.width : w / 2;
    paint(ctx, rasterize(pose, scaleX, w, h, style, x), style, px);
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return () => cancelAnimationFrame(raf);
}

/** Варианты пиксельного танцора. */
export const PIXEL_STYLES: PixelStyle[] = [
  {
    id: 'classic8',
    name: '8 бит · классика',
    height: 26,
    colors: {
      suit: '#3c3c4c',
      suitBack: '#2a2a36',
      skin: '#e8b88a',
      hat: '#3c3c4c',
      band: '#d6d6d6',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#000000',
    },
  },
  {
    id: 'outlined16',
    name: '16 бит · чёрный костюм со светлым контуром',
    height: 40,
    colors: {
      suit: '#2b2b3a',
      suitBack: '#1c1c28',
      skin: '#f0c49a',
      hat: '#24242e',
      band: '#c8232c',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#0b0b0b',
      outline: '#d8cfb8',
    },
  },
  {
    id: 'gameboy',
    name: 'Game Boy · 4 оттенка зелёного',
    height: 30,
    colors: {
      suit: '#0f380f',
      suitBack: '#306230',
      skin: '#8bac0f',
      hat: '#0f380f',
      band: '#9bbc0f',
      glove: '#9bbc0f',
      socks: '#9bbc0f',
      shoes: '#0f380f',
    },
  },
  {
    id: 'neon',
    name: 'Неон · аркадный автомат',
    height: 34,
    colors: {
      suit: '#160812',
      suitBack: '#2a0d22',
      skin: '#ffd2e8',
      hat: '#160812',
      band: '#ff2e88',
      glove: '#7df9ff',
      socks: '#7df9ff',
      shoes: '#ff2e88',
      outline: '#ff2e88',
    },
    glow: '#ff2e88',
  },
  {
    id: 'white',
    name: 'Белый костюм · Smooth Criminal',
    height: 36,
    colors: {
      suit: '#f2f2ee',
      suitBack: '#c9c9c2',
      skin: '#e8b88a',
      hat: '#f2f2ee',
      band: '#1b1b1b',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#f2f2ee',
      outline: '#1b1b1b',
    },
  },
  {
    id: 'mono',
    name: 'Силуэт · в цвет темы',
    height: 22,
    colors: {
      suit: '#ddd2bd',
      suitBack: '#8f8775',
      skin: '#ddd2bd',
      hat: '#b3121b',
      band: '#b3121b',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#ddd2bd',
    },
  },
];
