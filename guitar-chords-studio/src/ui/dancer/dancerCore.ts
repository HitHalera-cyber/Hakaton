// Движения танцора для экранов загрузки (рисует pixelDancer): 2D-человечек в шляпе. Пока полоса прогресса стоит — крутится
// и встаёт в узнаваемые позы; когда полоса движется — идёт «лунной походкой» (лицом назад,
// а сам скользит вперёд).

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

/** Угол (градусы, 0 — вниз, плюс — вперёд) от точки a к точке b. */
const angTo = (ax: number, ay: number, bx: number, by: number) => (Math.atan2(bx - ax, by - ay) * 180) / Math.PI;

/**
 * Нога по положению щиколотки (относительно таза, y вниз): бедро, колено, стопа для skeleton().
 * Колено сгибается вперёд. foot — угол стопы (0 — плоско, −60 — на носке).
 */
function legTo(ax: number, ay: number, foot: number): [number, number, number] {
  const d = Math.min(TH + SH - 0.01, Math.hypot(ax, ay));
  const toAnkle = angTo(0, 0, ax, ay);
  const alpha = (Math.acos((TH * TH + d * d - SH * SH) / (2 * TH * d)) * 180) / Math.PI;
  const hip = toAnkle + alpha;
  const kx = Math.sin(hip * R) * TH;
  const ky = Math.cos(hip * R) * TH;
  const shin = angTo(kx, ky, ax, ay);
  return [hip, hip - shin, foot];
}

const easeOut = (t: number) => 1 - (1 - t) ** 3;

/**
 * Лунная походка, как у Майкла: одна нога стоит на носке с согнутым коленом, другая — плоско
 * скользит назад; затем резкий «щелчок»: пятка опорной ноги падает, а скользившая встаёт на носок.
 * Щелчок короткий (15 % шага), скольжение — длинное и ровное. Корпус чуть вперёд, руки
 * полусогнуты, на щелчке — толчок плечами.
 */
function moonwalk(phase: number): Pose {
  const half = phase < 0.5 ? 0 : 1;
  const u = (phase % 0.5) / 0.5;
  const POP = 0.15;
  const FLOOR = TH + SH - 0.6;
  // Положения щиколоток: скользящая уезжает назад (+4 → −9), опорная (на носке) — вперёд (−9 → +4).
  const glide = u < POP ? 0 : (u - POP) / (1 - POP);
  const pop = u < POP ? easeOut(u / POP) : 1;
  const slideX = 7 - 19 * glide;
  const toeX = -12 + 19 * glide;
  // На щелчке: прежняя опорная (была на носке впереди) опускает пятку, прежняя скользящая (сзади) встаёт на носок.
  const slider = legTo(slideX, FLOOR - 1 - 7 * (1 - pop), -65 * (1 - pop));
  const toe = legTo(toeX, FLOOR - 1 - 7 * pop, -65 * pop);
  const [a, b] = half === 0 ? [slider, toe] : [toe, slider];
  const shrug = (1 - pop) * 6;
  const swing = Math.sin(2 * Math.PI * phase);
  return P(7, -6, -6, [22 + 14 * swing + shrug, 40], [-18 - 14 * swing - shrug, 35], a, b, shrug * 0.3);
}

/** Поза для вращения: колено поднято, руки прижаты. */
const SPIN_POSE = (): Pose => P(0, 0, 0, [40, 100], [-40, -100], [60, 110, -40], [0, 0, -50], 3);

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

/**
 * Движения танцора (без рисования): каждый кадр — поза и «поворот» (scaleX: 1 — лицом вправо,
 * −1 — влево, между ними — оборот вокруг себя).
 */
/** Вид танцора: сбоку (повернут по scaleX), спереди, со спины. */
export type View = 'side' | 'front' | 'back';

/** Кадры вращения: два оборота по 4 кадра — сбоку, спереди, другим боком, спиной. */
const SPIN_FRAMES: { view: View; scaleX: number }[] = [
  { view: 'side', scaleX: 1 },
  { view: 'front', scaleX: 1 },
  { view: 'side', scaleX: -1 },
  { view: 'back', scaleX: 1 },
];

export class DancerAnimator {
  private mode: 'pose' | 'walk' = 'pose';
  private walkPhase = 0;
  private idleT = 0;
  private poseIdx = 0;
  private from: Pose = STAND;
  private current: Pose = STAND;

  /**
   * Следующий кадр. rate — шагов лунной походки в секунду (чтобы ноги скользили со скоростью
   * полосы загрузки).
   */
  step(dt: number, moving: boolean, rate = 1.1): { pose: Pose; scaleX: number; view: View } {
    let pose: Pose;
    let scaleX = 1;
    let view: View = 'side';
    if (moving) {
      if (this.mode !== 'walk') {
        this.mode = 'walk';
        this.from = this.current;
        this.idleT = 0;
      }
      this.walkPhase = (this.walkPhase + dt * rate) % 1;
      this.idleT = Math.min(1, this.idleT + dt / 0.25);
      pose = lerpPose(this.from, moonwalk(this.walkPhase), ease(this.idleT));
      // Лицом назад (влево), а скользит вперёд (вправо).
      scaleX = -1;
    } else {
      if (this.mode !== 'pose') {
        this.mode = 'pose';
        this.from = this.current;
        this.idleT = 0;
      }
      // Цикл: вращение (покадрово, ~0,5 с) → поза (0,25 с переход + 1 с держать) → следующая.
      this.idleT += dt;
      const SPIN = 0.48;
      const IN = 0.18;
      const HOLD = 1.0;
      const cycle = SPIN + IN + HOLD;
      if (this.idleT >= cycle) {
        this.idleT -= cycle;
        this.poseIdx = (this.poseIdx + 1) % POSES.length;
        this.from = POSES[(this.poseIdx + POSES.length - 1) % POSES.length];
      }
      const target = POSES[this.poseIdx];
      if (this.idleT < SPIN) {
        // Вращение — раскадровка: 8 кадров (два оборота), без плавной «прокрутки» картинки.
        const f = SPIN_FRAMES[Math.floor((this.idleT / SPIN) * 8) % 4];
        pose = SPIN_POSE();
        view = f.view;
        scaleX = f.scaleX;
      } else {
        pose = lerpPose(SPIN_POSE(), target, easeOut(Math.min(1, (this.idleT - SPIN) / IN)));
      }
    }
    this.current = pose;
    return { pose, scaleX, view };
  }
}
