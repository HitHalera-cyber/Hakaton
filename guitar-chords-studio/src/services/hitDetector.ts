// Ловля ударов для «Ритма». Удар — резкий всплеск «верхов» (разностного сигнала): у нового удара
// верха свежие, а у звенящих струн они уже затухли. Поэтому удар виден и поверх звучащего аккорда,
// а медленные биения звенящих струн (громче-тише) ударами не считаются.
// Шумодав (filter) дополнительно отсеивает щелчки метронома из колонок и короткие стуки.

import { lowShare } from '../core/practice/timing';
import { rmsOf } from './mic';

/** Щелчок метронома — высокий писк: низов в нём меньше этой доли. */
const CLICK_LOW_SHARE = 0.55;
/** Блок анализа, отсчётов (~6 мс). */
const BLOCK = 256;

export class StrumHitDetector {
  /** Энергия верхов по блокам: время конца блока и энергия. */
  private blocks: { t: number; e: number }[] = [];
  private lastNow = -1;
  private floor = -1;
  private lastHit = -10;
  private candidate: { t: number; peak: number; at: number } | null = null;
  /** Насколько резким должен быть всплеск (во сколько раз громче, чем мгновение назад). */
  ratio = 2.6;
  /** Наименьший промежуток между ударами, с. */
  minGap = 0.12;

  constructor(public filter = false) {}

  /** Новый кадр микрофона (buf — последние отсчёты, now — время его конца). Возвращает время удара или null. */
  feed(buf: Float32Array, now: number, sampleRate: number): number | null {
    let out: number | null = null;
    const rms = rmsOf(buf, 512);
    const c = this.candidate;
    if (c) {
      c.peak = Math.max(c.peak, rms);
      // Кандидат ждёт ~70 мс: щелчок за это время затихает, а струна звучит дальше.
      if (now - c.at >= 0.07) {
        this.candidate = null;
        if (rms >= c.peak * 0.35) out = this.accept(c.t);
      }
    }
    // Новые отсчёты с прошлого кадра (кадры идут неравномерно, но буфер всегда «последний»).
    const fresh = this.lastNow < 0 ? buf.length : Math.min(buf.length - 1, Math.round((now - this.lastNow) * sampleRate));
    this.lastNow = now;
    const start = buf.length - Math.floor(fresh / BLOCK) * BLOCK;
    for (let from = Math.max(1, start); from + BLOCK <= buf.length; from += BLOCK) {
      let e = 0;
      for (let i = from; i < from + BLOCK; i++) {
        const d = buf[i] - buf[i - 1];
        e += d * d;
      }
      e /= BLOCK;
      const t = now - (buf.length - from - BLOCK) / sampleRate;
      const hit = this.block(t, e, t - BLOCK / sampleRate);
      if (hit == null) continue;
      if (!this.filter) {
        out = this.accept(hit) ?? out;
        continue;
      }
      const idx = Math.max(0, from - BLOCK);
      if (lowShare(buf, idx, sampleRate) >= CLICK_LOW_SHARE && !this.candidate) this.candidate = { t: hit, peak: rms, at: now };
    }
    return out;
  }

  /** Один блок: энергия e к моменту t. Возвращает время удара (начало блока), если он случился. */
  private block(t: number, e: number, startT: number): number | null {
    this.blocks.push({ t, e });
    while (this.blocks.length && this.blocks[0].t < t - 2) this.blocks.shift();
    // Фон — нижние 10% энергии за 2 с.
    if (this.blocks.length % 16 === 0 || this.floor < 0) {
      const sorted = this.blocks.map((b) => b.e).sort((a, b) => a - b);
      this.floor = sorted[Math.floor(sorted.length * 0.1)] ?? e;
    }
    if (this.blocks.length < 40) return null;
    // «Мгновение назад» — 25–90 мс до блока: шире, чем вступление струн одного удара.
    let ref = 0;
    let n = 0;
    for (let i = this.blocks.length - 2; i >= 0; i--) {
      const dt = t - this.blocks[i].t;
      if (dt > 0.09) break;
      if (dt >= 0.025) {
        ref += this.blocks[i].e;
        n++;
      }
    }
    if (!n) return null;
    ref /= n;
    if (!(e > ref * this.ratio && e > this.floor * 6 + 1e-9 && startT - this.lastHit > this.minGap)) return null;
    // Начало удара — раньше: первая струна вступает тише, чем весь удар. Идём назад, пока верха выше прежнего уровня.
    let begin = startT;
    for (let i = this.blocks.length - 2; i >= 0; i--) {
      const b = this.blocks[i];
      if (t - b.t > 0.06 || b.e < Math.max(ref * 1.35, e * 0.15)) break;
      begin = b.t - (t - startT);
    }
    return begin;
  }

  private accept(t: number): number | null {
    if (t - this.lastHit < this.minGap) return null;
    this.lastHit = t;
    return t;
  }
}
