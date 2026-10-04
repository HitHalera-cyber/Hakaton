// Танцор для экранов загрузки: 2D-человечек в шляпе. Пока полоса прогресса стоит — крутится
// и встаёт в узнаваемые позы; когда полоса движется — идёт «лунной походкой» (лицом назад,
// а сам скользит вперёд). Без React — чтобы работать и на заставке до загрузки программы.

/** Углы в градусах: 0 — вниз, плюс — вперёд (по направлению взгляда). */
export interface Pose {
  lean: number;
  head: number;
  hat: number;
  /** Плечо и локоть (локоть — относительно плеча). */
  armF: [number, number];
  armB: [number, number];
  /** Бедро, колено (относительно бедра), стопа (относительно голени; 0 — плоско, −80 — на носке). */
  legF: [number, number, number];
  legB: [number, number, number];
  /** Подъём тела (на носочки). */
  rise: number;
}

const P = (
  lean: number,
  head: number,
  hat: number,
  armF: [number, number],
  armB: [number, number],
  legF: [number, number, number],
  legB: [number, number, number],
  rise = 0,
): Pose => ({
  lean,
  head,
  hat,
  armF,
  armB,
  legF,
  legB,
  rise,
});

const STAND = P(0, 0, 0, [12, 10], [-12, -10], [4, 0, 0], [-4, 0, 0]);
/** Узнаваемые позы. */
const POSES: Pose[] = [
  // На носочках, колени вместе, рука у шляпы.
  P(-4, -6, -14, [150, 70], [-20, -20], [6, 8, -80], [-2, 8, -80], 7),
  // Наклон вперёд всем телом.
  P(34, 10, 6, [20, 0], [10, 0], [-28, 0, 28], [-34, 0, 34]),
  // Рука вверх, вторая на поясе, ноги врозь.
  P(-6, -10, -8, [168, 4], [-40, -110], [16, 0, 0], [-18, 0, 0]),
  // Выпад ногой вперёд, руки в стороны.
  P(-14, -4, -10, [95, 10], [-95, -10], [70, 30, 10], [-6, 0, 0]),
  // Шляпа набок, плечо вперёд, колено внутрь.
  P(8, 14, 22, [135, 95], [-30, -40], [12, 30, -30], [-8, 0, 0]),
];

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerpPose = (a: Pose, b: Pose, t: number): Pose => {
  const L = (x: number[], y: number[]) => x.map((v, i) => lerp(v, y[i], t));
  return {
    lean: lerp(a.lean, b.lean, t),
    head: lerp(a.head, b.head, t),
    hat: lerp(a.hat, b.hat, t),
    armF: L(a.armF, b.armF) as [number, number],
    armB: L(a.armB, b.armB) as [number, number],
    legF: L(a.legF, b.legF) as [number, number, number],
    legB: L(a.legB, b.legB) as [number, number, number],
    rise: lerp(a.rise, b.rise, t),
  };
};
const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

/** Лунная походка: фаза шага 0..1. Одна нога плоско скользит назад, другая — согнута, на носке. */
function moonwalk(phase: number): Pose {
  const leg = (p: number): [number, number, number] => {
    const s = Math.sin(2 * Math.PI * p);
    const bent = Math.max(0, s);
    // Скользящая нога уходит назад (минус), согнутая — впереди, на носке.
    return [-14 * Math.cos(2 * Math.PI * p) - 4, 38 * bent, -70 * bent];
  };
  const swing = Math.sin(2 * Math.PI * phase);
  return P(-3, -4, -6, [10 + 14 * swing, 20], [-10 - 14 * swing, -20], leg(phase), leg(phase + 0.5));
}

const R = Math.PI / 180;
const TH = 15;
const SH = 15;
const TORSO = 24;
const UP = 12;
const LOW = 12;

/** Пропорции фигуры (длины частей тела). */
export interface Dims {
  thigh: number;
  shin: number;
  torso: number;
  upper: number;
  lower: number;
  /** От шеи до центра головы. */
  neck: number;
  foot: number;
}
export const NORMAL: Dims = { thigh: TH, shin: SH, torso: TORSO, upper: UP, lower: LOW, neck: 8, foot: 7 };

/** Точки скелета для позы: таз в (0,0), y вниз. */
export function skeleton(p: Pose, d: Dims = NORMAL) {
  const dir = (deg: number, len: number, from: [number, number]): [number, number] => [
    from[0] + Math.sin(deg * R) * len,
    from[1] + Math.cos(deg * R) * len,
  ];
  const hip: [number, number] = [0, 0];
  const neck = dir(180 - p.lean, d.torso, hip); // корпус вверх
  const shoulder = dir(p.lean, 3, neck);
  const head = dir(180 - p.lean - p.head * 0.5, d.neck, neck);
  const arm = ([s, e]: [number, number]) => {
    const elbow = dir(s, d.upper, shoulder);
    return [shoulder, elbow, dir(s + e, d.lower, elbow)] as [number, number][];
  };
  const leg = ([h, k, f]: [number, number, number]) => {
    const knee = dir(h, d.thigh, hip);
    const ankle = dir(h - k, d.shin, knee);
    // Стопа: ровно вперёд (90°) при f = 0, вниз (носок) при −80.
    const toe = dir(90 + f + (h - k) * 0, d.foot, ankle);
    return [hip, knee, ankle, toe] as [number, number][];
  };
  return { hip, neck, head, armF: arm(p.armF), armB: arm(p.armB), legF: leg(p.legF), legB: leg(p.legB) };
}

export interface DancerState {
  /** Полоса движется — лунная походка; стоит — повороты и позы. */
  moving: boolean;
}

/**
 * Нарисовать танцора в svg (viewBox 0 0 W H) и запустить анимацию. Возвращает функцию остановки.
 * getState вызывается каждый кадр — так снаружи меняют «идёт / стоит» и положение.
 */
/**
 * Движения танцора (без рисования): каждый кадр — поза и «поворот» (scaleX: 1 — лицом вправо,
 * −1 — влево, между ними — оборот вокруг себя).
 */
export class DancerAnimator {
  private mode: 'pose' | 'walk' = 'pose';
  private walkPhase = 0;
  private idleT = 0;
  private poseIdx = 0;
  private from: Pose = STAND;
  private current: Pose = STAND;
  private facing = 1;

  step(dt: number, moving: boolean): { pose: Pose; scaleX: number } {
    let pose: Pose;
    let scaleX = 1;
    if (moving) {
      if (this.mode !== 'walk') {
        this.mode = 'walk';
        this.from = this.current;
        this.idleT = 0;
      }
      this.walkPhase = (this.walkPhase + dt / 0.9) % 1;
      this.idleT = Math.min(1, this.idleT + dt / 0.25);
      pose = lerpPose(this.from, moonwalk(this.walkPhase), ease(this.idleT));
      // Лицом назад (влево), а скользит вперёд (вправо).
      scaleX = -1;
      this.facing = -1;
    } else {
      if (this.mode !== 'pose') {
        this.mode = 'pose';
        this.from = this.current;
        this.idleT = 0;
      }
      // Цикл: поворот на месте (0,7 с) → поза (0,35 с переход + 0,9 с держать) → следующая.
      this.idleT += dt;
      const SPIN = 0.7;
      const IN = 0.35;
      const HOLD = 0.9;
      const cycle = SPIN + IN + HOLD;
      if (this.idleT >= cycle) {
        this.idleT -= cycle;
        this.poseIdx = (this.poseIdx + 1) % POSES.length;
        this.from = POSES[(this.poseIdx + POSES.length - 1) % POSES.length];
      }
      const target = POSES[this.poseIdx];
      const spinPose = P(0, 0, 0, [70, 10], [-70, -10], [2, 0, -40], [-2, 0, -40], 4);
      if (this.idleT < SPIN) {
        const t = this.idleT / SPIN;
        // Поворот: руки в стороны, тело «сжимается» по ширине — оборот вокруг себя.
        pose = lerpPose(this.from, spinPose, Math.min(1, t * 2.5));
        scaleX = Math.cos(t * 2 * Math.PI) * this.facing;
      } else {
        pose = lerpPose(spinPose, target, ease(Math.min(1, (this.idleT - SPIN) / IN)));
        this.facing = 1;
      }
    }
    this.current = pose;
    return { pose, scaleX };
  }
}

export function startDancer(svg: SVGSVGElement, getState: () => DancerState & { x?: number }): () => void {
  const NS = 'http://www.w3.org/2000/svg';
  svg.innerHTML = '';
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('class', 'dancer-body');
  svg.appendChild(g);
  const path = (cls: string) => {
    const e = document.createElementNS(NS, 'path');
    e.setAttribute('class', cls);
    g.appendChild(e);
    return e;
  };
  const back = path('dancer-limb back');
  const torso = path('dancer-limb');
  const front = path('dancer-limb');
  const head = document.createElementNS(NS, 'circle');
  head.setAttribute('r', '5.2');
  head.setAttribute('class', 'dancer-head');
  g.appendChild(head);
  const hat = path('dancer-hat');

  let raf = 0;
  let last = performance.now();
  const anim = new DancerAnimator();
  const pts = (list: [number, number][]) => list.map((q, i) => `${i ? 'L' : 'M'}${q[0].toFixed(2)} ${q[1].toFixed(2)}`).join('');

  const frame = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const st = getState();
    const { pose, scaleX } = anim.step(dt, st.moving);
    const sk = skeleton(pose);
    // Опора: ниже всех — стопа, она стоит на «полу».
    const feet = [...sk.legF, ...sk.legB].map((q) => q[1]);
    const floor = Math.max(...feet);
    const W = svg.viewBox.baseVal.width || 60;
    const H = svg.viewBox.baseVal.height || 86;
    const x = st.x ?? W / 2;
    g.setAttribute(
      'transform',
      `translate(${x.toFixed(2)} ${(H - 2 - floor).toFixed(2)}) scale(${(Math.abs(scaleX) < 0.08 ? 0.08 * Math.sign(scaleX || 1) : scaleX).toFixed(3)} 1)`,
    );
    back.setAttribute('d', pts(sk.armB) + pts(sk.legB));
    torso.setAttribute('d', pts([sk.hip, sk.neck]));
    front.setAttribute('d', pts(sk.armF) + pts(sk.legF));
    head.setAttribute('cx', sk.head[0].toFixed(2));
    head.setAttribute('cy', sk.head[1].toFixed(2));
    // Федора: поля и тулья, наклонены вместе с головой.
    const [hx, hy] = sk.head;
    hat.setAttribute(
      'd',
      `M${hx - 8} ${hy - 3.6} L${hx + 8} ${hy - 4.4} M${hx - 4.6} ${hy - 4} L${hx - 3.8} ${hy - 10} L${hx + 4.2} ${hy - 10.4} L${hx + 4.6} ${hy - 4.3}`,
    );
    hat.setAttribute('transform', `rotate(${(pose.hat - pose.lean * 0.6).toFixed(1)} ${hx} ${hy})`);
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return () => cancelAnimationFrame(raf);
}
