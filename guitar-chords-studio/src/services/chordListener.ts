// Распознавание того, что звучит с гитары: аккорд, отдельная нота или интервал. Два режима:
//  • «По удару» — после каждого удара результат готов за ~0,5 с;
//  • «Держите аккорд» — звук копится несколько секунд, и выдаётся один уверенный результат.
// Для плохого микрофона: шум комнаты запоминается, пока гитара молчит, и вычитается из спектра;
// строй гитары (если она вся чуть выше/ниже 440 Гц) оценивается по звуку и учитывается.
// Результаты идут в хранилище (для экрана) и в шину 'chord:heard' / 'notes:heard' (гриф, круг, уроки).

import { LIVE_VOCAB, buildModels, type RecognizedChord } from '../core/analysis/chordRecognition';
import { SEMI_COUNT, SpectrumAnalyzer, tuningFromVector } from '../core/analysis/dsp';
import { recognizeSound, type HeardNotes, type SoundResult } from '../core/analysis/liveSound';
import { store } from '../store';
import { bus } from './bus';
import { MIC_FRAME, OnsetDetector, mic, rmsOf } from './mic';

/** Режим «по удару»: когда начинать анализ после удара и сколько слушать. */
const START_AFTER = 0.36;
const LISTEN_FOR = 1.8;
/** Во сколько раз шум «с запасом» вычитается из спектра. */
const NOISE_OVER = 2;

class ChordListenerService {
  private raf: number | null = null;
  private models = buildModels(LIVE_VOCAB);

  get active() {
    return this.raf != null;
  }

  async start() {
    if (this.raf != null) return;
    const s = store.getState();
    s.setListen({ error: '', noiseReady: false, tuningCents: 0 });
    try {
      mic.setGain(s.settings.listen.gain);
      mic.setAutoGain(s.settings.listen.autoGain);
      await mic.setDevice(s.settings.listen.deviceId);
      await mic.acquire();
    } catch (e) {
      s.setListen({ error: e instanceof Error ? e.message : String(e) });
      return;
    }
    store.getState().setListen({ active: true });
    this.loop();
  }

  stop() {
    if (this.raf == null) return;
    cancelAnimationFrame(this.raf);
    this.raf = null;
    mic.release();
    store.getState().setListen({ active: false, level: 0, hold: { state: 'idle', progress: 0 } });
  }

  clearHistory() {
    store.getState().setListen({ history: [] });
  }

  private loop() {
    let spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate);
    const buf = new Float32Array(MIC_FRAME);
    // Накопленный спектр по полутонам (после вычитания шума) и число кадров в нём.
    const acc = { semi: new Float32Array(SEMI_COUNT), frames: 0 };
    const resetAcc = () => {
      acc.semi.fill(0);
      acc.frames = 0;
    };
    // Спектр шума (в единицах «до усиления», чтобы автоусиление его не искажало).
    const noise = new Float32Array(SEMI_COUNT);
    let noiseFrames = 0;
    let lastNoiseAt = 0;
    // Строй: сумма векторов отклонений пиков от нот (с медленным забыванием).
    const tun = { x: 0, y: 0 };
    const set = store.getState().setListen;

    const semiNow = () => {
      const g = mic.gain || 1;
      const { semi } = spectrum.semitones(buf, 0);
      for (let i = 0; i < semi.length; i++) semi[i] /= g;
      return semi;
    };
    const learnNoise = (now: number) => {
      if (now - lastNoiseAt < 0.25) return;
      lastNoiseAt = now;
      const semi = semiNow();
      const k = noiseFrames < 8 ? 1 / (noiseFrames + 1) : 0.1;
      for (let i = 0; i < SEMI_COUNT; i++) noise[i] += (semi[i] - noise[i]) * k;
      noiseFrames++;
      if (noiseFrames === 3) set({ noiseReady: true });
    };
    const trackTuning = () => {
      const [x, y] = spectrum.tuningVector(buf, 0);
      // tuningVector меряет отклонения от сетки A = 440, независимо от текущего строя анализатора.
      tun.x = tun.x * 0.97 + x;
      tun.y = tun.y * 0.97 + y;
      const t = tuningFromVector(tun.x, tun.y);
      if (Math.abs(t - spectrum.tuning) > 0.06) {
        spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate, t);
        set({ tuningCents: Math.round(t * 100) });
      }
    };
    const addFrame = (): SoundResult => {
      const semi = semiNow();
      const denoise = store.getState().settings.listen.denoise && noiseFrames >= 3;
      for (let i = 0; i < SEMI_COUNT; i++) acc.semi[i] += denoise ? Math.max(0, semi[i] - noise[i] * NOISE_OVER) : semi[i];
      acc.frames++;
      trackTuning();
      const r = recognizeSound(acc.semi, this.models);
      const chroma = new Array(12).fill(0);
      for (let i = 0; i < SEMI_COUNT; i++) chroma[(i + 24) % 12] += acc.semi[i];
      const max = Math.max(...chroma) || 1;
      set({ chroma: chroma.map((v) => v / max) });
      return r;
    };
    const emit = (r: SoundResult) => {
      if (r.notes) {
        set({ heardNotes: r.notes });
        bus.emit('notes:heard', r.notes);
        return;
      }
      const chord: RecognizedChord | null = r.best;
      if (!chord) return;
      // В список «сыграно» повтор того же аккорда не добавляем, а в шину — отправляем (уроки считают каждый удар).
      const h = store.getState().listen.history;
      if (h[0]?.symbol !== chord.symbol) set({ history: [chord, ...h].slice(0, 16) });
      set({ heardNotes: null });
      bus.emit('chord:heard', chord);
    };
    const keyOf = (r: SoundResult) => (r.notes ? notesKey(r.notes) : (r.best?.symbol ?? ''));

    const onsets = new OnsetDetector();
    let onsetAt = -10;
    let lastFrameAt = 0;
    let lastKey = '';
    let holdStart = -1;
    let lastSoundAt = -10;
    let emitted = false;

    const tick = () => {
      if (!mic.read(buf)) return;
      const { mode, sensitivity, holdSeconds } = store.getState().settings.listen;
      const rms = rmsOf(buf);
      set({ level: Math.min(1, rms * 6), gainNow: Math.round(mic.gain * 10) / 10 });
      const now = mic.now;
      onsets.sensitivity = sensitivity;
      const onset = onsets.feed(rms, now);
      const floor = onsets.noiseFloor;
      if (onset) {
        onsetAt = now;
        bus.emit('mic:onset', { time: now, level: rms });
      }
      // Тишина (гитара молчит уже полсекунды и больше) — учим шум комнаты.
      const quiet = rms < floor * 1.4 && now - onsetAt > 2 && now - lastSoundAt > 0.5;
      if (quiet) learnNoise(now);

      if (mode === 'strum') {
        if (onset) resetAcc();
        const since = now - onsetAt;
        if (since > START_AFTER && since < LISTEN_FOR && now - lastFrameAt > 0.09 && rms > floor * 1.5) {
          lastFrameAt = now;
          lastSoundAt = now;
          const r = addFrame();
          set({ result: r });
          const key = keyOf(r);
          if (key && acc.frames >= 2 && key !== lastKey) {
            lastKey = key;
            emit(r);
          }
        }
        if (onset) lastKey = '';
      } else {
        const sounding = onsets.ready && rms > Math.max(0.0015, floor * 2.2);
        if (sounding) lastSoundAt = now;
        if (onset && emitted) {
          holdStart = -1;
          emitted = false;
        }
        if (sounding && holdStart < 0) {
          holdStart = now;
          emitted = false;
          resetAcc();
        }
        if (holdStart >= 0 && !emitted) {
          const held = now - holdStart;
          if (held > 0.25 && now - lastFrameAt > 0.1 && sounding) {
            lastFrameAt = now;
            set({ result: addFrame() });
          }
          const progress = Math.min(1, held / holdSeconds);
          set({ hold: { state: 'listening', progress } });
          if (progress >= 1 && acc.frames >= 3) {
            const r = recognizeSound(acc.semi, this.models);
            emitted = true;
            set({ result: r, hold: { state: 'done', progress: 1 } });
            emit(r);
          }
        }
        if (holdStart >= 0 && now - lastSoundAt > 0.5) {
          if (!emitted) set({ hold: { state: 'short', progress: 0 } });
          holdStart = -1;
          emitted = false;
        }
      }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }
}

const notesKey = (n: HeardNotes) => n.midis.join(',');

export const chordListener = new ChordListenerService();
