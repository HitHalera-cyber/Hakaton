// Распознавание того, что звучит с гитары: аккорд, отдельная нота или интервал. Три режима:
//  • «По удару» — после каждого удара результат готов за ~0,5 с (нейросеть — за ~1 с);
//  • «Держите аккорд» — звук копится несколько секунд, и выдаётся один уверенный результат;
//  • «По струнам» — струны щиплются по одной от 6-й к 1-й: получается точная аппликатура.
// Два движка: формулы (спектр по полутонам) и нейросеть Basic Pitch (по записи последних секунд).
// Для плохого микрофона: шум комнаты запоминается, пока гитара молчит, и вычитается из спектра;
// строй гитары оценивается по звуку; калибровка поднимает басы, которые «съедает» микрофон.
// Результаты идут в хранилище (для экрана) и в шину 'chord:heard' / 'notes:heard' (гриф, круг, уроки).

import { applyGains } from '../core/analysis/calibration';
import { LIVE_VOCAB, buildModels, type RecognizedChord } from '../core/analysis/chordRecognition';
import { SEMI_COUNT, SpectrumAnalyzer, tuningFromVector } from '../core/analysis/dsp';
import { exactChord, recognizeNotes, recognizeSound, type HeardNotes, type SoundResult } from '../core/analysis/liveSound';
import { PluckTracker, fretsToTab, pluckFromSpectra, solveFingering, type Pluck } from '../core/analysis/stringPick';
import { boardFromFrets, soundingNotes, type Frets } from '../core/music/fretboard';
import { store } from '../store';
import { bus } from './bus';
import { MIC_FRAME, OnsetDetector, attackOf, mic, rmsOf } from './mic';
import { neural } from './neural';

/** Режим «по удару»: когда начинать анализ после удара и сколько слушать. */
const START_AFTER = 0.36;
const LISTEN_FOR = 1.8;
/** Нейросеть: сколько слушать после удара. */
const NEURAL_LISTEN = 1.0;
/** Во сколько раз шум «с запасом» вычитается из спектра. */
const NOISE_OVER = 2;
/** «По струнам»: через сколько после щипка брать спектр и сколько ждать следующего щипка. */
const PLUCK_POST = 0.2;
const PLUCK_TIMEOUT = 1.5;

class ChordListenerService {
  private raf: number | null = null;
  private models = buildModels(LIVE_VOCAB);

  get active() {
    return this.raf != null;
  }

  async start() {
    if (this.raf != null) return;
    const s = store.getState();
    const l = s.settings.listen;
    s.setListen({ error: '', noiseReady: false, tuningCents: 0, strings: { plucks: [], result: null } });
    try {
      mic.setGain(l.gain);
      mic.setAutoGain(l.autoGain);
      mic.keepHistory(l.engine === 'neural' ? 2.6 : 0);
      await mic.setDevice(l.deviceId);
      await mic.acquire();
    } catch (e) {
      s.setListen({ error: e instanceof Error ? e.message : String(e) });
      return;
    }
    store.getState().setListen({ active: true });
    if (l.engine === 'neural') void this.loadNeural();
    this.loop();
  }

  /** Подготовить нейросеть (при выборе движка или старте). */
  async loadNeural() {
    const set = store.getState().setListen;
    if (store.getState().listen.neural === 'ready') return true;
    set({ neural: 'loading' });
    try {
      const m = await neural.load();
      set({
        neural: 'ready',
        neuralBackend: m.backend === 'webgl' ? 'видеокарта' : m.backend === 'wasm' ? 'процессор, WebAssembly' : 'процессор',
      });
      return true;
    } catch (e) {
      set({ neural: 'error', error: 'Нейросеть не загрузилась: ' + (e instanceof Error ? e.message : String(e)) });
      return false;
    }
  }

  stop() {
    if (this.raf == null) return;
    cancelAnimationFrame(this.raf);
    this.raf = null;
    mic.keepHistory(0);
    mic.release();
    store.getState().setListen({ active: false, level: 0, hold: { state: 'idle', progress: 0 } });
  }

  clearHistory() {
    store.getState().setListen({ history: [] });
  }

  private loop() {
    const cal = () => store.getState().settings.listen.calibration;
    let spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate, (cal()?.tuningCents ?? 0) / 100);
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
    const listen = () => store.getState().settings.listen;

    /** Спектр по полутонам сейчас: без усиления микрофона, с калибровкой и (по желанию) без шума. */
    const semiNow = (denoise = false) => {
      const g = mic.gain || 1;
      const { semi } = spectrum.semitones(buf, 0);
      for (let i = 0; i < semi.length; i++) semi[i] /= g;
      if (denoise && listen().denoise && noiseFrames >= 3)
        for (let i = 0; i < SEMI_COUNT; i++) semi[i] = Math.max(0, semi[i] - noise[i] * NOISE_OVER);
      return applyGains(semi, cal()?.gains);
    };
    const learnNoise = (now: number) => {
      if (now - lastNoiseAt < 0.25) return;
      lastNoiseAt = now;
      const g = mic.gain || 1;
      const { semi } = spectrum.semitones(buf, 0);
      const k = noiseFrames < 8 ? 1 / (noiseFrames + 1) : 0.1;
      for (let i = 0; i < SEMI_COUNT; i++) noise[i] += (semi[i] / g - noise[i]) * k;
      noiseFrames++;
      if (noiseFrames === 3) set({ noiseReady: true });
    };
    const trackTuning = () => {
      const [x, y] = spectrum.tuningVector(buf, 0);
      tun.x = tun.x * 0.97 + x;
      tun.y = tun.y * 0.97 + y;
      const t = tuningFromVector(tun.x, tun.y);
      if (Math.abs(t - spectrum.tuning) > 0.06) {
        spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate, t);
        set({ tuningCents: Math.round(t * 100) });
      }
    };
    const showChroma = (semi: Float32Array) => {
      const chroma = new Array(12).fill(0);
      for (let i = 0; i < SEMI_COUNT; i++) chroma[(i + 24) % 12] += semi[i];
      const max = Math.max(...chroma) || 1;
      set({ chroma: chroma.map((v) => v / max) });
    };
    const addFrame = (): SoundResult => {
      const semi = semiNow(true);
      for (let i = 0; i < SEMI_COUNT; i++) acc.semi[i] += semi[i];
      acc.frames++;
      trackTuning();
      showChroma(acc.semi);
      return recognizeSound(acc.semi, this.models);
    };
    const emit = (r: SoundResult, frets?: Frets) => {
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
      bus.emit('chord:heard', frets ? { ...chord, frets } : chord);
    };
    const keyOf = (r: SoundResult) => (r.notes ? notesKey(r.notes) : (r.best?.symbol ?? ''));

    // ---------- Нейросеть ----------
    let neuralBusy = false;
    /** Распознать нейросетью звук после удара в момент onsetTime. */
    const runNeural = async (onsetTime: number, listenSec: number, after: (r: SoundResult) => void, fresh = true) => {
      if (neuralBusy || store.getState().listen.neural !== 'ready') return;
      neuralBusy = true;
      set({ neural: 'busy' });
      try {
        const { audio, endTime } = mic.recent(2.6);
        const onsetSec = Math.max(0, audio.length / mic.sampleRate - (endTime - onsetTime));
        const g = store.getState().guitar();
        const t0 = performance.now();
        const notes = await neural.notes(audio, mic.sampleRate, onsetSec, listenSec, Math.min(...g.strings) + g.capo, fresh);
        set({ neuralMs: Math.round(performance.now() - t0) });
        const r = recognizeNotes(notes, this.models);
        if (this.raf != null) after(r);
      } catch (e) {
        set({ error: 'Ошибка нейросети: ' + (e instanceof Error ? e.message : String(e)) });
      } finally {
        neuralBusy = false;
        if (store.getState().listen.neural === 'busy') set({ neural: 'ready' });
      }
    };

    // ---------- По струнам ----------
    const tracker = new PluckTracker();
    let pending: { at: number; pre: Float32Array } | null = null;
    let plucks: Pluck[] = [];
    let lastPluckAt = -10;
    let lastChromaAt = 0;
    let lastHitAt = -10;
    const guitar = () => store.getState().guitar();
    const finishPluck = (post: Float32Array) => {
      if (!pending) return;
      const g = guitar();
      const lo = Math.min(...g.strings) + g.capo;
      const hi = Math.max(...g.strings) + g.capo + 15;
      const p = pluckFromSpectra(pending.pre, post, lo, hi);
      const prev = plucks[plucks.length - 1];
      // Повтор той же ноты почти сразу — это эхо прошлого щипка, а не новая струна.
      const echo = prev && p.midi != null && p.midi === prev.midi && pending.at - lastHitAt < 0.5;
      lastHitAt = pending.at;
      pending = null;
      if (echo) return;
      plucks.push(p);
      set({ strings: { plucks: plucks.map((x) => x.midi), result: null } });
    };
    const finishChord = () => {
      const g = guitar();
      const done = plucks;
      plucks = [];
      const heard = done.filter((p) => p.midi != null);
      if (!heard.length) return;
      if (heard.length === 1) {
        const r = recognizeNotes([{ midi: heard[0].midi!, strength: 1 }], this.models);
        set({ result: r, strings: { plucks: done.map((x) => x.midi), result: null } });
        emit(r);
        return;
      }
      const f = solveFingering(done, g.strings, g.capo);
      if (!f) {
        set({ strings: { plucks: done.map((x) => x.midi), result: null }, error: '' });
        return;
      }
      const midis = soundingNotes(boardFromFrets(f.frets, g.capo), g.strings, g.capo).map((n) => n.midi);
      const chord = exactChord(midis, 0.5 + 0.5 * f.confidence);
      const r: SoundResult = chord
        ? { ...chord, notes: null }
        : recognizeNotes(
            midis.map((m) => ({ midi: m, strength: 1 })),
            this.models,
          );
      set({
        result: r,
        strings: {
          plucks: done.map((x) => x.midi),
          result: {
            frets: f.frets,
            tab: fretsToTab(f.frets),
            symbol: r.best?.symbol ?? r.notes?.label ?? '?',
            nameRu: r.best?.nameRu ?? r.notes?.nameRu ?? 'Не похоже на аккорд',
            confidence: f.confidence,
          },
        },
      });
      if (r.best) emit(r, f.frets);
      else if (listen().showOnBoard && store.getState().songOpen === 0) store.getState().apply(boardFromFrets(f.frets, g.capo), false);
    };

    const onsets = new OnsetDetector();
    // «По струнам»: щипки поверх звенящих струн — по всплеску высоких частот, с короткой паузой.
    const plucksOn = new OnsetDetector(0.6, 0.16);
    let onsetAt = -10;
    let lastFrameAt = 0;
    let lastKey = '';
    let holdStart = -1;
    let lastSoundAt = -10;
    let emitted = false;
    let neuralOnset = -1;
    let lastMode = listen().mode;

    const tick = () => {
      if (!mic.read(buf)) return;
      const { mode, sensitivity, holdSeconds, engine } = listen();
      const useNeural = engine === 'neural' && mode !== 'strings';
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
      if (mode !== lastMode) {
        lastMode = mode;
        plucks = [];
        pending = null;
        tracker.reset();
        set({ strings: { plucks: [], result: null } });
      }
      // Тишина (гитара молчит уже полсекунды и больше) — учим шум комнаты.
      const quiet = rms < floor * 1.4 && now - onsetAt > 2 && now - lastSoundAt > 0.5;
      if (quiet) learnNoise(now);

      if (mode === 'strings') {
        plucksOn.sensitivity = Math.max(0.5, sensitivity);
        // Щипок — скачок громкости (басовые струны), всплеск верхов (поверх звенящих струн)
        // или новая нота в спектре. Громкость — без учёта автоусиления, иначе оно маскирует скачки.
        const attack = plucksOn.feed((attackOf(buf) * 3) / (mic.gain || 1), now);
        const semi = semiNow();
        if (pending && now - pending.at >= PLUCK_POST) {
          finishPluck(semi);
          lastPluckAt = now;
          lastSoundAt = now;
          if (plucks.length >= guitar().strings.length) finishChord();
        }
        const hit = tracker.feed(now, semi, onset || attack);
        if (hit) {
          if (pending) finishPluck(semi);
          if (plucks.length >= guitar().strings.length) finishChord();
          pending = hit;
        }
        if (now - lastChromaAt > 0.1) {
          lastChromaAt = now;
          showChroma(semi);
        }
        if (!pending && plucks.length && now - lastPluckAt > PLUCK_TIMEOUT) finishChord();
      } else if (mode === 'strum') {
        if (onset) {
          resetAcc();
          // Нейросеть: прошлый удар ещё не разобран, а прошло достаточно — разбираем его покороче.
          if (useNeural && neuralOnset >= 0 && now - neuralOnset > 0.45) {
            const at = neuralOnset;
            void runNeural(at, now - at - 0.05, (r) => (set({ result: r }), emit(r)));
          }
          neuralOnset = now;
        }
        const since = now - onsetAt;
        if (since > START_AFTER && since < LISTEN_FOR && now - lastFrameAt > 0.09 && rms > floor * 1.5) {
          lastFrameAt = now;
          lastSoundAt = now;
          const r = addFrame();
          if (!useNeural) {
            set({ result: r });
            const key = keyOf(r);
            if (key && acc.frames >= 2 && key !== lastKey) {
              lastKey = key;
              emit(r);
            }
          }
        }
        if (useNeural && neuralOnset >= 0 && now - neuralOnset > NEURAL_LISTEN + 0.1) {
          const at = neuralOnset;
          neuralOnset = -1;
          void runNeural(at, NEURAL_LISTEN, (r) => {
            set({ result: r });
            const key = keyOf(r);
            if (key && key !== lastKey) {
              lastKey = key;
              emit(r);
            }
          });
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
            const r = addFrame();
            if (!useNeural) set({ result: r });
          }
          const progress = Math.min(1, held / holdSeconds);
          set({ hold: { state: 'listening', progress } });
          if (progress >= 1 && acc.frames >= 3) {
            emitted = true;
            set({ hold: { state: 'done', progress: 1 } });
            // Аккорд звучит давно — берём последние ~1,3 с, без сравнения «до/после удара».
            if (useNeural) void runNeural(now - 1.35, 1.3, (r) => (set({ result: r }), emit(r)), false);
            else {
              const r = recognizeSound(acc.semi, this.models);
              set({ result: r });
              emit(r);
            }
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
