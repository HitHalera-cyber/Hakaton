// Распознавание аккордов с гитары. Два режима:
//  • «По удару» — после каждого удара аккорд распознаётся за ~0,5 с;
//  • «Держите аккорд» — звук копится несколько секунд, и выдаётся один уверенный результат.
// Результаты идут в хранилище (для экрана) и в шину 'chord:heard' (для грифа, круга, уроков, статистики).

import { LIVE_VOCAB, buildModels, recognizeChord, type RecognizedChord } from '../core/analysis/chordRecognition';
import { SpectrumAnalyzer } from '../core/analysis/dsp';
import { store } from '../store';
import { bus } from './bus';
import { MIC_FRAME, OnsetDetector, mic, rmsOf } from './mic';

/** Режим «по удару»: когда начинать анализ после удара и сколько слушать. */
const START_AFTER = 0.36;
const LISTEN_FOR = 1.8;

class ChordListenerService {
  private raf: number | null = null;
  private models = buildModels(LIVE_VOCAB);

  get active() {
    return this.raf != null;
  }

  async start() {
    if (this.raf != null) return;
    const s = store.getState();
    s.setListen({ error: '' });
    try {
      mic.setGain(s.settings.listen.gain);
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
    const spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate);
    const buf = new Float32Array(MIC_FRAME);
    const acc = { chroma: new Float32Array(12), bass: new Float32Array(12), frames: 0 };
    const resetAcc = () => {
      acc.chroma.fill(0);
      acc.bass.fill(0);
      acc.frames = 0;
    };
    const set = store.getState().setListen;
    const addFrame = () => {
      const f = spectrum.frame(buf, 0);
      for (let i = 0; i < 12; i++) {
        acc.chroma[i] += f.chroma[i];
        acc.bass[i] += f.bass[i];
      }
      acc.frames++;
      const r = recognizeChord(acc.chroma, acc.bass, this.models);
      const max = Math.max(...acc.chroma) || 1;
      set({ chroma: [...acc.chroma].map((v) => v / max) });
      return r;
    };
    const emit = (chord: RecognizedChord) => {
      // В список «сыграно» повтор того же аккорда не добавляем, а в шину — отправляем (уроки считают каждый удар).
      const h = store.getState().listen.history;
      if (h[0]?.symbol !== chord.symbol) set({ history: [chord, ...h].slice(0, 16) });
      bus.emit('chord:heard', chord);
    };

    const onsets = new OnsetDetector();
    let onsetAt = -10;
    let lastFrameAt = 0;
    let lastSymbol = '';
    let holdStart = -1;
    let lastSoundAt = -10;
    let emitted = false;

    const tick = () => {
      if (!mic.read(buf)) return;
      const { mode, sensitivity, holdSeconds } = store.getState().settings.listen;
      const rms = rmsOf(buf);
      set({ level: Math.min(1, rms * 6) });
      const now = mic.now;
      onsets.sensitivity = sensitivity;
      const onset = onsets.feed(rms, now);
      const floor = onsets.noiseFloor;
      if (onset) {
        onsetAt = now;
        bus.emit('mic:onset', { time: now, level: rms });
      }

      if (mode === 'strum') {
        if (onset) resetAcc();
        const since = now - onsetAt;
        if (since > START_AFTER && since < LISTEN_FOR && now - lastFrameAt > 0.09 && rms > floor * 1.5) {
          lastFrameAt = now;
          const r = addFrame();
          set({ result: r });
          if (r.best && acc.frames >= 2 && r.best.symbol !== lastSymbol) {
            lastSymbol = r.best.symbol;
            emit(r.best);
          }
        }
        if (onset) lastSymbol = '';
      } else {
        const sounding = rms > Math.max(0.0015, floor * 2.2);
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
            const r = recognizeChord(acc.chroma, acc.bass, this.models);
            emitted = true;
            set({ result: r, hold: { state: 'done', progress: 1 } });
            if (r.best) emit(r.best);
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

export const chordListener = new ChordListenerService();
