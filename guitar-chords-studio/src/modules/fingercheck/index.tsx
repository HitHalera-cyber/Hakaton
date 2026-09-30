import '../../ui/practice.css';
import { useEffect, useRef, useState } from 'react';
import { checkFingering, type FingerCheckResult, type StringStatus } from '../../core/analysis/fingerCheck';
import { SpectrumAnalyzer } from '../../core/analysis/dsp';
import { midiName, pcName } from '../../core/music/notes';
import { MIC_FRAME, mic, OnsetDetector, rmsOf } from '../../services/mic';
import { useGuitar } from '../../store';
import type { ModuleDef } from '../types';

type Phase = 'idle' | 'waiting' | 'listening' | 'done';

const STATUS: Record<StringStatus, { icon: string; text: string; cls: string }> = {
  ok: { icon: '✓', text: 'звучит чисто', cls: '' },
  weak: { icon: '⚠', text: 'звучит слабо — палец приглушает струну или прижат не у лада', cls: 'warn' },
  missing: { icon: '✗', text: 'не звучит — струну глушит соседний палец', cls: 'bad' },
  wrong: { icon: '✗', text: 'звучит не та нота — струна не прижата или прижата не на том ладу', cls: 'bad' },
  silent: { icon: '✓', text: 'молчит, как и должна', cls: '' },
  ringing: { icon: '✗', text: 'звенит, хотя должна молчать — заглушите её', cls: 'bad' },
};

/** Проверка аппликатуры: какие струны аккорда звучат чисто, а какие — нет. */
function FingerCheckView() {
  const g = useGuitar();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState<FingerCheckResult | null>(null);
  const raf = useRef<number | null>(null);

  const n = g.strings.length;
  const expected = Array.from({ length: n }, (_, s) => ({
    string: s,
    midi: g.boardNotes.find((x) => x.string === s)?.midi ?? null,
    openMidi: g.strings[s] + g.capo,
  }));
  const hasChord = expected.some((e) => e.midi != null);

  const stop = () => {
    if (raf.current != null) {
      cancelAnimationFrame(raf.current);
      raf.current = null;
      mic.release();
    }
  };
  useEffect(() => stop, []);

  const check = async () => {
    setError('');
    setResult(null);
    try {
      await mic.acquire();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setPhase('waiting');
    const spectrum = new SpectrumAnalyzer(MIC_FRAME, mic.sampleRate);
    const buf = new Float32Array(MIC_FRAME);
    const acc = new Float32Array(spectrum.semitones(buf).semi.length);
    const onsets = new OnsetDetector(0.55);
    const target = expected.map((e) => ({ ...e }));
    let onsetAt = -1;
    let frames = 0;
    let lastFrame = 0;
    const tick = () => {
      if (!mic.read(buf)) return;
      const now = mic.now;
      const rms = rmsOf(buf);
      if (onsetAt < 0 && onsets.feed(rms, now)) {
        onsetAt = now;
        setPhase('listening');
      }
      // Спустя 0,3 с после удара (сам удар шумный) копим спектр ~0,8 с.
      if (onsetAt >= 0 && now - onsetAt > 0.3 && now - lastFrame > 0.09) {
        lastFrame = now;
        const { semi } = spectrum.semitones(buf);
        for (let i = 0; i < acc.length; i++) acc[i] += semi[i];
        frames++;
      }
      if (frames >= 8) {
        stop();
        setResult(checkFingering(acc, target));
        setPhase('done');
        return;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };

  return (
    <div className="tab-body">
      <p className="hint">
        Поставьте аккорд на гриф (кликом, из справочника или песенника), нажмите «Проверить» и один раз ударьте по струнам. Программа
        скажет, какие струны звучат чисто, а какие глушатся.
      </p>
      <div className="pr-row">
        <div className="pr-target">
          <span className="sym">{g.result.primary?.symbol ?? (hasChord ? '?' : '—')}</span>
          <small className="hint">{hasChord ? 'аккорд на грифе' : 'поставьте аккорд на гриф'}</small>
        </div>
        <button className="btn primary" disabled={!hasChord || phase === 'waiting' || phase === 'listening'} onClick={() => void check()}>
          🎤 Проверить
        </button>
        {(phase === 'waiting' || phase === 'listening') && (
          <>
            <span className="listening-note">{phase === 'waiting' ? '● Ударьте по струнам…' : '● Слушаю звучание…'}</span>
            <button className="btn small" onClick={() => (stop(), setPhase('idle'))}>
              Отмена
            </button>
          </>
        )}
      </div>
      {error && <p className="error">{error}</p>}

      {result && (
        <div className="fc-result">
          <div className="pr-cards">
            <div className="pr-card">
              <small>Чисто звучат</small>
              <span className="pr-big">
                {result.good}/{result.total}
              </span>
            </div>
          </div>
          <div className="fc-strings">
            {[...result.strings].reverse().map((s) => {
              const st = STATUS[s.status];
              return (
                <div key={s.string} className={`fc-string ${st.cls}`}>
                  <b>{n - s.string}</b>
                  <span className="fc-note">{s.midi != null ? midiName(s.midi) : `× ${pcName(g.strings[s.string] + g.capo)}`}</span>
                  <span className="fc-icon">{st.icon}</span>
                  <span className="fc-text">
                    {st.text}
                    {s.heard != null && ` (слышно ${midiName(s.heard)})`}
                  </span>
                  {s.midi != null && (
                    <div className="pr-bar fc-level">
                      <span className={st.cls} style={{ width: `${Math.round(s.level * 100)}%` }} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {result.extras.length > 0 && (
            <p className="error">
              Лишние ноты: {result.extras.map(midiName).join(', ')} — задета соседняя струна или палец стоит не на том ладу.
            </p>
          )}
          {result.good === result.total && result.extras.length === 0 && <p className="ok-text">Отлично: аккорд звучит чисто!</p>}
        </div>
      )}
    </div>
  );
}

export const fingercheckModule: ModuleDef = {
  id: 'fingercheck',
  title: 'Проверка аппликатуры',
  icon: '🩺',
  group: 'practice',
  description: 'Какая струна глушится или звенит в сыгранном аккорде',
  keywords: ['чисто', 'глушится', 'дребезг', 'баррэ', 'звенит'],
  View: FingerCheckView,
  isNew: true,
};
