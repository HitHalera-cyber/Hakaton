// Общий микрофон. Слушать гитару, тюнер, ритм, подбор мелодии, уроки — все берут звук отсюда:
// поток открывается один раз и закрывается, когда его отпустил последний пользователь.

import { audio } from '../core/audio/engine';

/** Окно анализа ~0,34 с при 48 кГц: хватает, чтобы различать соседние полутоны в басу. */
export const MIC_FRAME = 16384;

class MicService {
  private stream: MediaStream | null = null;
  private gainNode: GainNode | null = null;
  private analyserNode: AnalyserNode | null = null;
  private users = 0;
  private starting: Promise<void> | null = null;
  private gainValue = 3;

  get active() {
    return this.analyserNode != null;
  }
  get analyser() {
    return this.analyserNode;
  }
  get sampleRate() {
    return audio.context.sampleRate;
  }
  get now() {
    return audio.context.currentTime;
  }

  setGain(g: number) {
    this.gainValue = g;
    if (this.gainNode) this.gainNode.gain.value = g;
  }

  /** Взять микрофон. Бросает понятную ошибку, если доступа нет. */
  async acquire(): Promise<void> {
    this.users++;
    if (this.analyserNode) return;
    this.starting ??= this.open();
    try {
      await this.starting;
    } catch (e) {
      this.users--;
      throw e;
    } finally {
      this.starting = null;
    }
  }

  release() {
    this.users = Math.max(0, this.users - 1);
    if (this.users === 0) this.close();
  }

  /** Последние N отсчётов звука (N ≤ MIC_FRAME). */
  read(buf: Float32Array<ArrayBuffer>): boolean {
    if (!this.analyserNode) return false;
    if (buf.length === MIC_FRAME) this.analyserNode.getFloatTimeDomainData(buf);
    else {
      const full = (this.scratch ??= new Float32Array(MIC_FRAME));
      this.analyserNode.getFloatTimeDomainData(full);
      buf.set(full.subarray(MIC_FRAME - buf.length));
    }
    return true;
  }
  private scratch: Float32Array<ArrayBuffer> | null = null;

  private async open() {
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      const ctx = audio.context;
      const src = ctx.createMediaStreamSource(s);
      const gain = ctx.createGain();
      gain.gain.value = this.gainValue;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = MIC_FRAME;
      analyser.smoothingTimeConstant = 0;
      src.connect(gain).connect(analyser);
      this.stream = s;
      this.gainNode = gain;
      this.analyserNode = analyser;
    } catch (e) {
      throw new Error(
        e instanceof Error && e.name === 'NotAllowedError'
          ? 'Нет доступа к микрофону. В Windows: Параметры → Конфиденциальность → Микрофон → разрешить приложениям доступ.'
          : 'Не удалось включить микрофон: ' + (e instanceof Error ? e.message : String(e)),
      );
    }
  }

  private close() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.gainNode = null;
    this.analyserNode = null;
  }
}

export const mic = new MicService();

/** Громкость (RMS) последних n отсчётов буфера. */
export function rmsOf(buf: Float32Array, n = 2048): number {
  let sum = 0;
  const from = Math.max(0, buf.length - n);
  for (let i = from; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.sqrt(sum / (buf.length - from));
}

/**
 * Детектор ударов по струнам: удар — резкий скачок громкости относительно фона и относительно
 * того, что звучало мгновение назад (затухающий аккорд тоже громче фона, но не растёт).
 */
export class OnsetDetector {
  private floor = 0.001;
  private lastOnset = -10;
  private recent: { t: number; rms: number }[] = [];
  constructor(
    public sensitivity = 0.5,
    public refractory = 0.25,
  ) {}

  get noiseFloor() {
    return this.floor;
  }

  /** Возвращает true, если в момент now случился удар. */
  feed(rms: number, now: number): boolean {
    const threshold = 3.5 - this.sensitivity * 2.2;
    const jump = 2.2 - this.sensitivity * 0.8;
    while (this.recent.length && this.recent[0].t < now - 0.25) this.recent.shift();
    const before = this.recent.filter((r) => r.t < now - 0.03);
    const recentMin = before.length ? Math.min(...before.map((r) => r.rms)) : 0;
    this.recent.push({ t: now, rms });
    const onset = rms > Math.max(0.002, this.floor * threshold) && rms > recentMin * jump && now - this.lastOnset > this.refractory;
    if (onset) this.lastOnset = now;
    else if (rms < this.floor * 2) this.floor = this.floor * 0.97 + rms * 0.03;
    return onset;
  }
}
