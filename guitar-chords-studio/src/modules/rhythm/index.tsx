import '../../ui/practice.css';
import { useEffect, useRef, useState } from 'react';
import { audio } from '../../core/audio/engine';
import {
  HIT_NEAR_MS,
  HIT_OK_MS,
  attackIndex,
  beatError,
  classifyHit,
  hitStreak,
  lowShare,
  median,
  timingAdvice,
  timingSummary,
} from '../../core/practice/timing';
import { bus } from '../../services/bus';
import { metronome } from '../../services/metronome';
import { mic, OnsetDetector, rmsOf } from '../../services/mic';
import { store, usePick } from '../../store';
import type { ModuleDef } from '../types';

const RANGE_MS = 120;
/** Меньше такой доли низких частот — это щелчок метронома, а не струны. */
const CLICK_LOW_SHARE = 0.55;
/** Сколько ударов собрать для подстройки задержки. */
const TUNE_HITS = 8;

/** Задержка по умолчанию: вывод звука (как сообщает система) + ввод с микрофона (~15 мс). */
function defaultLatency() {
  const ctx = audio.context as AudioContext & { outputLatency?: number };
  return Math.round(((ctx.outputLatency ?? 0) + (ctx.baseLatency ?? 0)) * 1000 + 15);
}

/**
 * Тренировка ритма: метроном щёлкает, вы играете в долю (или восьмыми), микрофон ловит каждый удар
 * и показывает, насколько вы раньше или позже щелчка.
 */
function RhythmView() {
  const { rhythm, patchRhythm, best, running } = usePick((s) => ({
    rhythm: s.settings.rhythm,
    patchRhythm: s.patchRhythm,
    best: s.practice.rhythmBest,
    running: s.metro.running,
  }));
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');
  const [sub, setSub] = useState(1);
  // Задержка по умолчанию — то, что сообщает система о колонках, плюс типичная задержка микрофона.
  const latency = rhythm.latencyMs ?? defaultLatency();
  const setLatency = (ms: number) => patchRhythm({ latencyMs: ms });
  // Подстройка задержки: сколько ударов собрано (null — не идёт).
  const [tuning, setTuning] = useState<number[] | null>(null);
  const tuningRef = useRef<number[] | null>(null);
  tuningRef.current = tuning;
  const [errors, setErrors] = useState<number[]>([]);
  // Текущая доля такта — для огоньков (−1 — метроном молчит).
  const [beat, setBeat] = useState(-1);
  const [hitAt, setHitAt] = useState(0);
  const beats = useRef<number[]>([]);
  const raf = useRef<number | null>(null);
  const opts = useRef({ sub, latency });
  opts.current = { sub, latency };

  useEffect(
    () =>
      bus.on('metronome:beat', (b) => {
        beats.current = [...beats.current, b.time].slice(-16);
        // Событие приходит заранее (по расписанию) — огонёк зажигаем в момент щелчка.
        window.setTimeout(() => setBeat(b.beat), Math.max(0, (b.time - mic.now) * 1000));
      }),
    [],
  );
  useEffect(() => {
    if (!running) setBeat(-1);
  }, [running]);
  useEffect(() => () => stop(), []);

  const start = async () => {
    setError('');
    try {
      await mic.acquire();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setErrors([]);
    if (!metronome.running) metronome.start();
    setActive(true);
    const onsets = new OnsetDetector(0.6, 0.1);
    const buf = new Float32Array(2048);
    // Кандидат в удары ждёт ~70 мс: щелчок метронома (если микрофон слышит колонки) за это время
    // затихает, а струна звучит дальше — так щелчки не принимаются за удары.
    let candidate: { t: number; peak: number; at: number } | null = null;
    const tick = () => {
      if (!mic.read(buf)) return;
      const now = mic.now;
      const rms = rmsOf(buf, 512);
      if (candidate) {
        candidate.peak = Math.max(candidate.peak, rms);
        if (now - candidate.at >= 0.07) {
          const c = candidate;
          candidate = null;
          if (rms >= c.peak * 0.35) onHit(c.t);
        }
      }
      if (onsets.feed(rms, now) && !candidate) {
        // Точный момент удара — по отсчётам внутри буфера, а не по кадру экрана.
        const idx = attackIndex(buf);
        // Щелчок метронома из колонок (высокий писк) — не удар; забываем его, чтобы не мешал поймать удар сразу за ним.
        if (lowShare(buf, idx, mic.sampleRate) < CLICK_LOW_SHARE) onsets.forget();
        else candidate = { t: now - (buf.length - idx) / mic.sampleRate, peak: rms, at: now };
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  /** Удар в момент t (по часам звука, без поправки на задержку). */
  const onHit = (t: number) => {
    const tun = tuningRef.current;
    if (tun) {
      // Подстройка: ошибка без поправки — это и есть задержка.
      const err = beatError(t, beats.current, metronome.beatDuration, 1);
      if (err == null) return;
      const next = [...tun, err];
      if (next.length >= TUNE_HITS) {
        const ms = Math.round(Math.max(0, Math.min(300, median(next) * 1000)));
        setLatency(ms);
        setTuning(null);
        setErrors([]);
        store.getState().toast(`Задержка подстроена: ${ms} мс`);
      } else setTuning(next);
      return;
    }
    const err = beatError(t - opts.current.latency / 1000, beats.current, metronome.beatDuration, opts.current.sub);
    if (err != null) {
      setErrors((list) => [...list, err].slice(-64));
      setHitAt(Date.now());
    }
  };

  const stop = () => {
    if (raf.current == null) return;
    cancelAnimationFrame(raf.current);
    raf.current = null;
    mic.release();
    metronome.stop();
    setActive(false);
    setErrors((list) => {
      const s = timingSummary(list);
      if (s && s.count >= 8 && store.getState().setRhythmBest(s.accuracy))
        store.getState().toast(`Новый рекорд точности: ±${s.accuracy} мс`);
      return list;
    });
  };

  const summary = timingSummary(errors.slice(-24));
  const advice = summary && summary.count >= 4 ? timingAdvice(summary) : null;
  const last = errors.length ? errors[errors.length - 1] : null;
  const hit = last != null ? classifyHit(last) : null;
  const streak = hitStreak(errors);
  const pos = (e: number) => `${50 + (Math.max(-RANGE_MS, Math.min(RANGE_MS, e * 1000)) / RANGE_MS) * 50}%`;
  const zoneW = (ms: number) => `${(ms / RANGE_MS) * 100}%`;

  return (
    <div className="tab-body">
      <p className="hint">
        Бейте по струнам точно в щелчок метронома. После каждого удара крупно видно: в долю, рано или поздно. Зелёная зона — попали.
      </p>
      <div className="pr-row">
        {active ? (
          <button className="btn" onClick={stop}>
            ■ Стоп
          </button>
        ) : (
          <button className="btn primary" onClick={() => void start()}>
            ▶ Начать
          </button>
        )}
        <label className="field inline">
          <span>Темп</span>
          <input type="range" min={40} max={200} value={rhythm.bpm} onChange={(e) => patchRhythm({ bpm: Number(e.target.value) })} />
          <b>{rhythm.bpm}</b>
        </label>
        <div className="segmented" role="radiogroup" aria-label="Сетка">
          <button className={sub === 1 ? 'on' : ''} onClick={() => setSub(1)} title="Удар на каждый щелчок">
            Четверти
          </button>
          <button className={sub === 2 ? 'on' : ''} onClick={() => setSub(2)} title="Удар на щелчок и между щелчками">
            Восьмые
          </button>
        </div>
        <label className="field inline" title="Щелчок доходит из колонок, а звук гитары — в микрофон с задержкой. Её программа вычитает">
          <span>Задержка звука</span>
          <input type="range" min={0} max={300} step={5} value={latency} onChange={(e) => setLatency(Number(e.target.value))} />
          <b>{latency} мс</b>
        </label>
        <button
          className="btn"
          disabled={tuning != null}
          title="Сыграйте 8 ударов ровно в щелчок — программа сама вычислит задержку вашего компьютера"
          onClick={async () => {
            if (!active) await start();
            setTuning([]);
          }}
        >
          🎯 Подстроить задержку
        </button>
        {running && !active && <span className="hint">метроном играет</span>}
      </div>
      {error && <p className="error">{error}</p>}
      {tuning != null && (
        <div className="rh-advice near">
          <b>
            Подстройка задержки: {tuning.length} из {TUNE_HITS}
          </b>
          <span>Бейте по струнам ровно в щелчок, как слышите его. Программа измерит, на сколько звук запаздывает в вашем компьютере.</span>
        </div>
      )}
      {rhythm.latencyMs == null && tuning == null && (
        <p className="hint">
          Совет: сначала нажмите «🎯 Подстроить задержку» — у каждого компьютера она своя, и без подстройки удары кажутся мимо. Лучше играть
          в наушниках, чтобы микрофон не слышал щелчки.
        </p>
      )}

      <div className="rh-stage">
        <div className="rh-beats" title="Доли такта: горит та, что звучит сейчас">
          {Array.from({ length: rhythm.meter }, (_, i) => (
            <span key={i} className={`${i === beat ? 'on' : ''} ${i === 0 ? 'first' : ''}`}>
              {i + 1}
            </span>
          ))}
        </div>
        <div key={hitAt} className={`rh-hit ${hit ? hit.zone : 'idle'}`}>
          {hit ? hit.text : active ? 'Играйте в щелчок…' : 'Нажмите «Начать»'}
        </div>
        <div className="rh-streak">{streak >= 2 ? `🔥 ${streak} подряд в долю` : '\u00a0'}</div>
      </div>

      <div className="pr-meter rh-meter" title="Последние удары относительно щелчка">
        <i className="zone near" style={{ left: `calc(50% - ${zoneW(HIT_NEAR_MS)} / 2 * 1)`, width: zoneW(HIT_NEAR_MS) }} />
        <i className="zone ok" style={{ left: `calc(50% - ${zoneW(HIT_OK_MS)} / 2 * 1)`, width: zoneW(HIT_OK_MS) }} />
        {errors.slice(-12, -1).map((e, i, arr) => (
          <span key={errors.length - arr.length - 1 + i} className="old" style={{ left: pos(e) }} />
        ))}
        {last != null && <span key={hitAt} className={`now ${hit!.zone}`} style={{ left: pos(last) }} />}
        <span className="lbl" style={{ left: 4 }}>
          ← рано
        </span>
        <span className="lbl" style={{ left: '50%', transform: 'translateX(-50%)' }}>
          щелчок
        </span>
        <span className="lbl" style={{ right: 4 }}>
          поздно →
        </span>
      </div>

      {advice && (
        <div className={`rh-advice ${advice.zone}`}>
          <b>{advice.title}</b>
          <span>{advice.tip}</span>
        </div>
      )}

      <div className="pr-cards" style={{ marginTop: 14 }}>
        <div className="pr-card">
          <small>Точность</small>
          <span className="pr-big">{summary ? `±${summary.accuracy}` : '—'}</span>
          <small>мс, последние 24 удара (меньше — лучше)</small>
        </div>
        <div className="pr-card">
          <small>Ударов</small>
          <b>{errors.length}</b>
        </div>
        <div className="pr-card">
          <small>Рекорд</small>
          <b>{best != null ? `±${best} мс` : '—'}</b>
        </div>
      </div>
    </div>
  );
}

export const rhythmModule: ModuleDef = {
  id: 'rhythm',
  title: 'Ритм',
  icon: '🥁',
  group: 'practice',
  description: 'Игра с метрономом: насколько вы спешите или отстаёте — по микрофону',
  keywords: ['метроном', 'доля', 'спешу', 'отстаю', 'бой'],
  View: RhythmView,
};
