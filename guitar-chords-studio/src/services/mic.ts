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
  /** Запись последних секунд звука (для нейросети нужно больше, чем окно анализатора). */
  private historySeconds = 0;
  private ring: Float32Array | null = null;
  private ringPos = 0;
  private ringFilled = 0;
  private ringAt = 0;
  private proc: ScriptProcessorNode | null = null;
  private deviceId = '';
  /** Автоусиление: множитель к ручному усилению, подстраивается под громкость игры. */
  private autoGain = false;
  private autoFactor = 1;
  private peak = 0;
  private lastAuto = 0;
  /** Уровень шума без игры (пики тишины, до усиления). */
  private noiseRaw = 0;

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

  /** Итоговое усиление (ручное × автоматическое). */
  get gain() {
    return this.gainValue * (this.autoGain ? this.autoFactor : 1);
  }

  setGain(g: number) {
    this.gainValue = g;
    this.applyGain();
  }

  setAutoGain(on: boolean) {
    if (on === this.autoGain) return;
    this.autoGain = on;
    this.autoFactor = 1;
    this.peak = 0;
    this.noiseRaw = 0;
    this.applyGain();
  }

  private applyGain() {
    if (this.gainNode) this.gainNode.gain.value = this.gain;
  }

  /** Хранить последние seconds секунд звука (0 — не хранить). */
  keepHistory(seconds: number) {
    this.historySeconds = seconds;
    if (this.gainNode) this.attachHistory();
  }

  /**
   * Последние seconds секунд звука (после усиления) и момент (по часам AudioContext),
   * на который приходится последний отсчёт. Пусто, если запись не включена.
   */
  recent(seconds: number): { audio: Float32Array; endTime: number } {
    const ring = this.ring;
    if (!ring) return { audio: new Float32Array(0), endTime: this.now };
    const n = Math.min(this.ringFilled, Math.floor(seconds * this.sampleRate));
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) out[i] = ring[(this.ringPos - n + i + ring.length) % ring.length];
    return { audio: out, endTime: this.ringAt };
  }

  private attachHistory() {
    this.proc?.disconnect();
    this.proc = null;
    this.ring = null;
    if (!this.historySeconds || !this.gainNode) return;
    const ctx = audio.context;
    const ring = new Float32Array(Math.ceil(this.historySeconds * ctx.sampleRate));
    this.ring = ring;
    this.ringPos = 0;
    this.ringFilled = 0;
    // ScriptProcessor устарел, но работает везде (Electron, Android) и не требует отдельного файла.
    const proc = ctx.createScriptProcessor(2048, 1, 1);
    proc.onaudioprocess = (e) => {
      const x = e.inputBuffer.getChannelData(0);
      for (let i = 0; i < x.length; i++) {
        ring[this.ringPos] = x[i];
        this.ringPos = (this.ringPos + 1) % ring.length;
      }
      this.ringFilled = Math.min(ring.length, this.ringFilled + x.length);
      // Последний отсчёт буфера записан «только что» — по часам контекста это примерно сейчас.
      this.ringAt = ctx.currentTime;
    };
    // Выход молчит (буфер не заполняем), но подключение к выходу нужно, чтобы обработчик вызывался.
    this.gainNode.connect(proc);
    proc.connect(ctx.destination);
    this.proc = proc;
  }

  /** Выбрать микрофон ('' — системный). Если он уже открыт — переоткрывается с новым устройством. */
  async setDevice(id: string) {
    if (id === this.deviceId) return;
    this.deviceId = id;
    if (!this.analyserNode) return;
    this.close();
    await this.open();
  }

  /** Доступные микрофоны (названия видны после того, как доступ к микрофону разрешён). */
  async devices(): Promise<{ id: string; label: string }[]> {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    const list = await navigator.mediaDevices.enumerateDevices();
    return list
      .filter((d) => d.kind === 'audioinput' && d.deviceId !== 'default' && d.deviceId !== 'communications')
      .map((d, i) => ({ id: d.deviceId, label: d.label || `Микрофон ${i + 1}` }));
  }

  /**
   * Автоусиление: следим за пиками игры (быстро вниз при перегрузе, медленно вверх, когда тихо)
   * и держим пики около 0,25. В тишине усиление не растёт — иначе раздуется шум.
   */
  private trackAutoGain(buf: Float32Array) {
    // Не чаще 20 раз в секунду, сколько бы модулей ни читали звук.
    if (this.now - this.lastAuto < 0.05) return;
    this.lastAuto = this.now;
    let p = 0;
    for (let i = Math.max(0, buf.length - 2048); i < buf.length; i++) p = Math.max(p, Math.abs(buf[i]));
    const raw = p / this.gain;
    // Шум: быстро вниз, медленно вверх (~×1,2 в секунду) — игра его почти не поднимает.
    this.noiseRaw = !this.noiseRaw || raw < this.noiseRaw ? raw : this.noiseRaw * 1.01;
    const playing = raw > this.noiseRaw * 4;
    if (playing) this.peak = Math.max(raw, this.peak * 0.995);
    const target = 0.25;
    if (p > 0.9) this.autoFactor *= 0.7;
    // Подстраиваемся только пока звучит игра, а не тишина.
    else if (playing && raw >= this.peak * 0.5) {
      // Но шум не раздуваем выше 0,02.
      const noiseCap = 0.02 / (this.noiseRaw * this.gainValue);
      const want = Math.min(30 / this.gainValue, noiseCap, Math.max(1 / this.gainValue, target / (this.peak * this.gainValue)));
      // Вверх — медленно, вниз — быстрее.
      this.autoFactor += (want - this.autoFactor) * (want > this.autoFactor ? 0.01 : 0.08);
    }
    this.applyGain();
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
    if (this.autoGain) this.trackAutoGain(buf);
    return true;
  }
  private scratch: Float32Array<ArrayBuffer> | null = null;

  private async open() {
    try {
      const base = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
      const s = await navigator.mediaDevices
        .getUserMedia({ audio: this.deviceId ? { ...base, deviceId: { exact: this.deviceId } } : base })
        // Выбранный микрофон отключён — берём системный.
        .catch((e) => {
          if (!this.deviceId || (e as Error).name === 'NotAllowedError') throw e;
          return navigator.mediaDevices.getUserMedia({ audio: base });
        });
      const ctx = audio.context;
      const src = ctx.createMediaStreamSource(s);
      const gain = ctx.createGain();
      gain.gain.value = this.gain;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = MIC_FRAME;
      analyser.smoothingTimeConstant = 0;
      src.connect(gain).connect(analyser);
      this.stream = s;
      this.gainNode = gain;
      this.analyserNode = analyser;
      this.attachHistory();
    } catch (e) {
      throw new Error(
        e instanceof Error && e.name === 'NotAllowedError'
          ? 'Нет доступа к микрофону. В Windows: Параметры → Конфиденциальность → Микрофон → разрешить приложениям доступ.'
          : 'Не удалось включить микрофон: ' + (e instanceof Error ? e.message : String(e)),
      );
    }
  }

  private close() {
    this.proc?.disconnect();
    this.proc = null;
    this.ring = null;
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
 * «Атака» последних n отсчётов: громкость разностного сигнала (подчёркивает высокие частоты).
 * У нового щипка верха свежие, а у уже звенящих струн они быстро затухают — поэтому так видно
 * щипок даже поверх звучащего аккорда (а общая громкость при этом почти не растёт).
 */
export function attackOf(buf: Float32Array, n = 1024): number {
  let sum = 0;
  const from = Math.max(1, buf.length - n);
  for (let i = from; i < buf.length; i++) {
    const d = buf[i] - buf[i - 1];
    sum += d * d;
  }
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
  /** Громкость за последние секунды — по ней считается фон (шум комнаты и микрофона). */
  private long: { t: number; rms: number }[] = [];
  private floorAt = -1;
  private startedAt = -1;
  constructor(
    public sensitivity = 0.5,
    public refractory = 0.25,
  ) {}

  get noiseFloor() {
    return this.floor;
  }
  /** Фон уже измерен (прошли первые полсекунды). */
  get ready() {
    return this.startedAt >= 0 && this.long.length > 0 && this.long[this.long.length - 1].t - this.startedAt >= 0.6;
  }

  /** Возвращает true, если в момент now случился удар. */
  feed(rms: number, now: number): boolean {
    // Первые полсекунды только слушаем фон: без истории любой шум выглядел бы ударом.
    if (this.startedAt < 0) this.startedAt = now;
    if (now - this.startedAt < 0.6) {
      this.recent.push({ t: now, rms });
      this.floorAt = -1;
      this.trackFloor(rms, now);
      return false;
    }
    const threshold = 3.5 - this.sensitivity * 2.2;
    const jump = 2.2 - this.sensitivity * 0.8;
    while (this.recent.length && this.recent[0].t < now - 0.25) this.recent.shift();
    const before = this.recent.filter((r) => r.t < now - 0.03);
    const recentMin = before.length ? Math.min(...before.map((r) => r.rms)) : 0;
    this.recent.push({ t: now, rms });
    const onset = rms > Math.max(0.002, this.floor * threshold) && rms > recentMin * jump && now - this.lastOnset > this.refractory;
    if (onset) this.lastOnset = now;
    this.trackFloor(rms, now);
    return onset;
  }

  /**
   * Фон — 5-й процентиль громкости за 15 секунд: тихие моменты между ударами. Раньше фон мог
   * только опускаться, и у шумного микрофона шум считался игрой.
   */
  private trackFloor(rms: number, now: number) {
    this.long.push({ t: now, rms });
    while (this.long.length && this.long[0].t < now - 15) this.long.shift();
    if (now - this.floorAt < 0.25) return;
    this.floorAt = now;
    const sorted = this.long.map((r) => r.rms).sort((a, b) => a - b);
    const p5 = sorted[Math.floor(sorted.length * 0.05)] ?? rms;
    this.floor = Math.max(0.0002, p5);
  }
}
