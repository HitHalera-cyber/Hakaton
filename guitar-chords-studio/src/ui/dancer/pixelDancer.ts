// Пиксельный танцор в разных рисовках: те же движения (DancerAnimator), но разные пропорции,
// «кисть» и фон — классический спрайт, чиби, блоки, 1-бит с растром, палочник, ЖК-игрушка, силуэт на луне.

import { DancerAnimator, NORMAL, skeleton, type Dims, type Pose } from './dancerCore';

type Ink = 'suit' | 'suitBack' | 'shade' | 'skin' | 'hat' | 'band' | 'glove' | 'socks' | 'shoes' | 'eye' | 'outline';
const INKS: Ink[] = ['suit', 'suitBack', 'shade', 'skin', 'hat', 'band', 'glove', 'socks', 'shoes', 'eye', 'outline'];

export type PixelKind = 'sprite' | 'chibi' | 'blocky' | 'dither' | 'stick' | 'lcd' | 'moon';

export interface PixelStyle {
  id: string;
  kind: PixelKind;
  name: string;
  note: string;
  /** Высота фигуры в «пикселях». */
  height: number;
  colors: Partial<Record<Ink, string>>;
  /** Цвет фона (бумага, экран, луна). */
  bg?: string;
  dims?: Dims;
  /** Толщина конечностей относительно обычной. */
  limb?: number;
  /** Размер головы относительно обычной. */
  head?: number;
}

class Raster {
  data: Uint8Array;
  square = false;
  constructor(
    public w: number,
    public h: number,
  ) {
    this.data = new Uint8Array(w * h);
  }
  set(x: number, y: number, ink: number) {
    if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.data[y * this.w + x] = ink;
  }
  dot(x: number, y: number, r: number, ink: number) {
    const x0 = Math.floor(x - r);
    const x1 = Math.ceil(x + r);
    const y0 = Math.floor(y - r);
    const y1 = Math.ceil(y + r);
    for (let yy = y0; yy <= y1; yy++)
      for (let xx = x0; xx <= x1; xx++) {
        const inside = this.square
          ? Math.abs(xx + 0.5 - x) <= r && Math.abs(yy + 0.5 - y) <= r
          : (xx + 0.5 - x) ** 2 + (yy + 0.5 - y) ** 2 <= r * r;
        if (inside) this.set(xx, yy, ink);
      }
  }
  ring(x: number, y: number, r: number, ink: number) {
    for (let a = 0; a < 64; a++)
      this.set(Math.floor(x + Math.cos((a / 64) * 2 * Math.PI) * r), Math.floor(y + Math.sin((a / 64) * 2 * Math.PI) * r), ink);
  }
  line(a: [number, number], b: [number, number], r: number, ink: number, from = 0, to = 1) {
    const n = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) * 2));
    for (let i = 0; i <= n; i++) {
      const t = from + ((to - from) * i) / n;
      this.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, r, ink);
    }
  }
  /** Контур снаружи фигуры. */
  outline(ink: number) {
    const src = this.data.slice();
    for (let y = 0; y < this.h; y++)
      for (let x = 0; x < this.w; x++) {
        if (src[y * this.w + x]) continue;
        for (const [dx, dy] of [
          [1, 0],
          [-1, 0],
          [0, 1],
          [0, -1],
        ]) {
          const v = src[(y + dy) * this.w + x + dx];
          if (x + dx >= 0 && x + dx < this.w && y + dy >= 0 && y + dy < this.h && v && v !== ink) {
            this.data[y * this.w + x] = ink;
            break;
          }
        }
      }
  }
  /** Тень: пиксели краски from на «теневой» стороне (справа-снизу от света) красятся в to. */
  shade(from: number, to: number) {
    const src = this.data.slice();
    for (let y = 0; y < this.h; y++)
      for (let x = 0; x < this.w; x++)
        if (src[y * this.w + x] === from && (x + 1 >= this.w || src[y * this.w + x + 1] !== from)) this.data[y * this.w + x] = to;
  }
}

/** Нарисовать позу в растр W×H; x — центр по горизонтали, ноги — у нижнего края. */
export function rasterize(pose: Pose, scaleX: number, w: number, h: number, style: PixelStyle, x = w / 2): Raster {
  const R = new Raster(w, h);
  R.square = style.kind === 'blocky';
  const d = style.dims ?? NORMAL;
  const tall = d.thigh + d.shin + d.torso + d.neck + 12 * (style.head ?? 1);
  const k = style.height / tall;
  const sk = skeleton(pose, d);
  const floor = Math.max(...[...sk.legF, ...sk.legB].map((q) => q[1]));
  const sx = Math.abs(scaleX) < 0.12 ? 0.12 * Math.sign(scaleX || 1) : scaleX;
  const T = (q: [number, number]): [number, number] => [x + q[0] * k * sx, h - 1 - (floor - q[1]) * k];
  const ink = (n: Ink) => (style.colors[n] ? INKS.indexOf(n) + 1 : style.colors.suit ? INKS.indexOf('suit') + 1 : 1);
  const thin = style.kind === 'stick';
  const limb = thin ? 0.5 : Math.max(0.75, 1.5 * k * (style.limb ?? 1));
  const leg = (l: [number, number][], back: boolean) => {
    const [hip, knee, ankle, toe] = l.map(T);
    const c = ink(back ? 'suitBack' : 'suit');
    R.line(hip, knee, limb * 1.15, c);
    R.line(knee, ankle, limb * 1.1, c, 0, thin ? 1 : 0.72);
    if (!thin) R.line(knee, ankle, limb * 0.95, ink('socks'), 0.72, 1);
    R.line(ankle, toe, limb * 1.05, ink('shoes'));
  };
  const arm = (a: [number, number][], back: boolean, gloved: boolean) => {
    const [sh, el, hand] = a.map(T);
    const c = ink(back ? 'suitBack' : 'suit');
    R.line(sh, el, limb, c);
    R.line(el, hand, limb * 0.95, c, 0, thin ? 1 : 0.72);
    if (!thin) R.line(el, hand, limb * 1.15, ink(gloved ? 'glove' : 'skin'), 0.72, 1);
  };
  leg(sk.legB, true);
  arm(sk.armB, true, false);
  R.line(T(sk.hip), T(sk.neck), thin ? 0.5 : limb * (style.kind === 'chibi' ? 2.4 : 1.9), ink('suit'));
  leg(sk.legF, false);
  arm(sk.armF, false, true);
  const head = T(sk.head);
  const hr = 5.4 * k * (style.head ?? 1);
  if (thin) R.ring(head[0], head[1], hr, ink('suit'));
  else R.dot(head[0], head[1], hr, ink('skin'));
  if (style.colors.eye) {
    // Глаза смотрят туда, куда повёрнут танцор.
    const dir = Math.sign(sx);
    R.set(Math.floor(head[0] + dir * hr * 0.35), Math.floor(head[1]), ink('eye'));
    if (Math.abs(sx) > 0.5) R.set(Math.floor(head[0] + dir * hr * 0.75), Math.floor(head[1]), ink('eye'));
  }
  // Федора: поля, тулья, лента.
  const hk = k * (style.head ?? 1);
  const tilt = ((pose.hat - pose.lean * 0.6) * Math.PI) / 180;
  const rot = (dx: number, dy: number): [number, number] => [
    head[0] + (dx * Math.cos(tilt) - dy * Math.sin(tilt)) * hk * sx,
    head[1] + (dx * Math.sin(tilt) + dy * Math.cos(tilt)) * hk,
  ];
  R.line(rot(-8.5, -3.8), rot(8.5, -4.4), Math.max(0.5, 1.1 * hk), ink('hat'));
  if (!thin) for (let dy = -10.5; dy <= -4; dy += 0.8) R.line(rot(-4.4, dy), rot(4.4, dy), Math.max(0.5, 0.8 * hk), ink('hat'));
  else R.line(rot(-4.4, -10), rot(4.4, -10), 0.5, ink('hat'));
  if (style.colors.band) R.line(rot(-4.4, -5.6), rot(4.4, -5.6), Math.max(0.5, 0.7 * hk), ink('band'));
  if (style.colors.shade) R.shade(ink('suit'), ink('shade'));
  if (style.colors.outline) R.outline(ink('outline'));
  return R;
}

/** Нарисовать растр: каждый «пиксель» — квадрат px×px (с особенностями рисовки). */
export function paint(ctx: CanvasRenderingContext2D, R: Raster, style: PixelStyle, px: number, ghost?: Raster) {
  const pal = INKS.map((n) => style.colors[n] ?? style.colors.suit ?? '#fff');
  const W = R.w * px;
  const H = R.h * px;
  if (style.kind === 'lcd') {
    ctx.fillStyle = style.bg ?? '#b6c39f';
    ctx.fillRect(0, 0, W, H);
  }
  if (style.kind === 'dither') {
    ctx.fillStyle = style.bg ?? '#f2f0e6';
    ctx.fillRect(0, 0, W, H);
  }
  if (style.kind === 'moon') {
    // Луна из пикселей позади танцора.
    const cx = R.w / 2;
    const cy = R.h * 0.42;
    const r = R.h * 0.42;
    for (let y = 0; y < R.h; y++)
      for (let x = 0; x < R.w; x++) {
        const dd = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
        if (dd <= r) {
          ctx.fillStyle = dd > r - 1.2 ? '#c9b98a' : (x * 7 + y * 13) % 23 === 0 ? '#d8cca4' : (style.bg ?? '#efe6c4');
          ctx.fillRect(x * px, y * px, px, px);
        }
      }
  }
  const gap = style.kind === 'lcd' ? Math.max(1, Math.floor(px / 5)) : 0;
  if (ghost) {
    // ЖК: «призрачные» сегменты, которые всегда чуть видны на экране.
    ctx.fillStyle = 'rgba(30,42,26,0.08)';
    for (let i = 0; i < ghost.data.length; i++)
      if (ghost.data[i]) ctx.fillRect((i % ghost.w) * px, Math.floor(i / ghost.w) * px, px - gap, px - gap);
  }
  for (let y = 0; y < R.h; y++)
    for (let x = 0; x < R.w; x++) {
      const v = R.data[y * R.w + x];
      if (!v) continue;
      const col = pal[v - 1];
      // 1-бит: тёмные краски — растром (шахматка), светлые — сплошные.
      if (style.kind === 'dither' && INKS[v - 1] === 'suitBack' && (x + y) % 2) continue;
      if (style.kind === 'dither' && INKS[v - 1] === 'shade' && (x + y) % 2) {
        ctx.fillStyle = style.bg ?? '#f2f0e6';
        ctx.fillRect(x * px, y * px, px, px);
        continue;
      }
      ctx.fillStyle = col;
      ctx.fillRect(x * px, y * px, px - gap, px - gap);
    }
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

/** Варианты рисовки пиксельного танцора. */
export const PIXEL_STYLES: PixelStyle[] = [
  {
    id: 'sprite',
    kind: 'sprite',
    name: 'Классический спрайт 16 бит',
    note: 'обычные пропорции, тени на костюме, контур',
    height: 44,
    colors: {
      suit: '#2e2e3e',
      shade: '#18181f',
      suitBack: '#22222c',
      skin: '#f0c49a',
      hat: '#24242e',
      band: '#d0d0d0',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#0b0b0b',
      eye: '#2a1a10',
      outline: '#cfc6b0',
    },
  },
  {
    id: 'chibi',
    kind: 'chibi',
    name: 'Чиби',
    note: 'большая голова, короткие ножки, глаза — как в японских играх',
    height: 40,
    dims: { thigh: 8, shin: 8, torso: 13, upper: 7, lower: 7, neck: 13, foot: 6 },
    head: 2.1,
    limb: 1.25,
    colors: {
      suit: '#262636',
      shade: '#14141c',
      suitBack: '#1c1c28',
      skin: '#ffd9b3',
      hat: '#1c1c26',
      band: '#e03a4a',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#000000',
      eye: '#1a1010',
      outline: '#f5ead2',
    },
  },
  {
    id: 'blocky',
    kind: 'blocky',
    name: 'Кубики',
    note: 'всё из квадратов, как в играх-«кубиках»',
    height: 30,
    limb: 1.35,
    head: 1.3,
    colors: {
      suit: '#3a3a52',
      shade: '#26263a',
      suitBack: '#2c2c40',
      skin: '#d9a77a',
      hat: '#2a2a3a',
      band: '#e8e8e8',
      glove: '#ffffff',
      socks: '#ffffff',
      shoes: '#141414',
      eye: '#3a2614',
    },
  },
  {
    id: 'dither',
    kind: 'dither',
    name: '1 бит на бумаге',
    note: 'только чёрное и белое, полутона — растром, как на старых компьютерах',
    height: 46,
    bg: '#f2f0e6',
    colors: {
      suit: '#111111',
      shade: '#111111',
      suitBack: '#111111',
      skin: '#f2f0e6',
      hat: '#111111',
      glove: '#f2f0e6',
      socks: '#f2f0e6',
      shoes: '#111111',
      outline: '#111111',
    },
  },
  {
    id: 'stick',
    kind: 'stick',
    name: 'Палочный человечек',
    note: 'тонкие линии в 1 пиксель, голова-кружок — «рисунок в тетради»',
    height: 50,
    colors: { suit: '#e8dfc8', hat: '#e8dfc8', shoes: '#e8dfc8' },
  },
  {
    id: 'lcd',
    kind: 'lcd',
    name: 'ЖК-игрушка «Электроника»',
    note: 'серо-зелёный экран, сегменты с промежутками и «призраки» выключенных точек',
    height: 34,
    bg: '#b6c39f',
    colors: { suit: '#1e2a1a', suitBack: '#2e3c28', skin: '#1e2a1a', hat: '#1e2a1a', glove: '#1e2a1a', socks: '#1e2a1a', shoes: '#1e2a1a' },
  },
  {
    id: 'moon',
    kind: 'moon',
    name: 'Силуэт на фоне луны',
    note: 'чёрная фигура на пиксельной луне — сразу в стиле «Нави»',
    height: 32,
    bg: '#efe6c4',
    colors: { suit: '#0b0b0f', suitBack: '#1c1a22', skin: '#0b0b0f', hat: '#0b0b0f', glove: '#0b0b0f', socks: '#0b0b0f', shoes: '#0b0b0f' },
  },
];
