import './record.css';
import { useEffect, useState, useSyncExternalStore } from 'react';
import { pickFile, safeName, saveFile } from '../../core/export/download';
import { encodeWav } from '../../core/export/wav';
import { mic, rmsOf } from '../../services/mic';
import { recorder, type Take } from '../../services/recorder';
import { store, usePick } from '../../store';
import type { ModuleDef } from '../types';
import { Waveform } from './Waveform';

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/** Уровень входа, пока идёт запись (чтобы видеть, что звук есть и не перегружен). */
function useInputLevel(active: boolean) {
  const [level, setLevel] = useState(0);
  useEffect(() => {
    if (!active) return;
    const buf = new Float32Array(2048);
    let raf = 0;
    const tick = () => {
      if (mic.read(buf)) {
        let peak = 0;
        for (const x of buf) peak = Math.max(peak, Math.abs(x));
        setLevel(Math.min(1, Math.max(rmsOf(buf) * 4, peak / Math.max(1, mic.gain))));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active]);
  return level;
}

function RecordView() {
  const st = useSyncExternalStore(recorder.subscribe, () => recorder.state);
  const { input } = usePick((s) => ({ input: s.settings.listen.input }));
  const [withMetronome, setWithMetronome] = useState(false);
  const [withRef, setWithRef] = useState(true);
  const [normalize, setNormalize] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [, tick] = useState(0);
  const recording = st.recording != null;
  const level = useInputLevel(recording);
  const take = st.takes.find((t) => t.id === selected) ?? st.takes[st.takes.length - 1] ?? null;

  // Таймер записи и бегунок.
  useEffect(() => {
    if (!recording && !st.playing) return;
    const id = window.setInterval(() => tick((x) => x + 1), 200);
    return () => window.clearInterval(id);
  }, [recording, st.playing]);
  // Ушли из раздела во время записи — дубль не теряем, а сохраняем.
  useEffect(
    () => () => {
      if (recorder.state.recording) recorder.finishRecording(true);
      recorder.stop();
    },
    [],
  );

  const start = async () => {
    setError('');
    try {
      await recorder.record({ withRef: withRef && st.reference != null, metronome: withMetronome });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const stop = () => {
    const t = recorder.finishRecording(normalize);
    if (t) setSelected(t.id);
    else store.getState().toast('Запись слишком короткая');
  };
  const save = (t: Take) => saveFile(encodeWav(t.samples, t.sampleRate, 24), `${safeName(t.name)}.wav`, 'audio/wav');
  const openRef = async () => {
    const f = await pickFile('audio/*,.mp3,.wav,.ogg,.flac,.m4a,.aac');
    if (!f) return;
    try {
      await recorder.setReference(f);
    } catch {
      setError('Не удалось прочитать файл. Поддерживаются MP3, WAV, OGG, FLAC, M4A/AAC.');
    }
  };

  const playingTake = st.playing?.takeId;
  const both = take != null && take.refAt != null && st.reference != null;

  return (
    <div className="tab-body rec">
      <p className="hint">
        Нажмите «Запись», сыграйте и послушайте себя. Откройте оригинал песни — можно играть под него (в наушниках) и сравнить: оригинал и
        дубль звучат вместе, ползунком выбираете, кого слышно громче. Дубль сохраняется в WAV без потери качества.
      </p>

      <div className="rec-ref">
        <span>
          Оригинал: <b>{st.reference ? st.reference.name : 'не выбран'}</b>
          {st.reference && <small> · {fmt(st.reference.buffer.duration)}</small>}
        </span>
        <button className="btn small" onClick={() => void openRef()} disabled={recording}>
          🎵 {st.reference ? 'Другой файл' : 'Открыть песню'}
        </button>
        {st.reference && (
          <button className="link" onClick={() => recorder.clearReference()} disabled={recording}>
            убрать
          </button>
        )}
      </div>

      <div className="rec-controls">
        {recording ? (
          <button className="btn rec-btn on" onClick={stop}>
            ■ Стоп <span className="rec-time">{fmt(mic.captured)}</span>
          </button>
        ) : (
          <button className="btn primary rec-btn" onClick={() => void start()}>
            ● Запись
          </button>
        )}
        <div className="rec-level" title="Уровень входа: зелёный — хорошо, красный — перегруз (убавьте усиление)">
          <span style={{ width: `${Math.round(level * 100)}%` }} className={level > 0.95 ? 'clip' : ''} />
        </div>
        <div className="rec-options">
          {st.reference && (
            <label className="check">
              <input type="checkbox" checked={withRef} disabled={recording} onChange={(e) => setWithRef(e.target.checked)} />
              Играть оригинал во время записи
            </label>
          )}
          <label className="check">
            <input type="checkbox" checked={withMetronome} disabled={recording} onChange={(e) => setWithMetronome(e.target.checked)} />
            Метроном
          </label>
          <label className="check" title="Тихую запись поднять до нормальной громкости">
            <input type="checkbox" checked={normalize} disabled={recording} onChange={(e) => setNormalize(e.target.checked)} />
            Выровнять громкость
          </label>
        </div>
      </div>
      <small className="hint">
        Звук: {input === 'line' ? 'кабель (звуковая карта)' : 'микрофон'} — выбирается в «Слушать аккорд». Под оригинал играйте в наушниках,
        иначе микрофон запишет и его.
      </small>
      {error && <p className="error">{error}</p>}

      {(take || st.reference) && (
        <div className="rec-compare">
          <Waveform take={take} />
          <div className="rec-play">
            {st.playing ? (
              <button className="btn" onClick={() => recorder.stop()}>
                ■ Стоп
              </button>
            ) : (
              <button className="btn primary" onClick={() => recorder.play(take?.id ?? null, 0)} disabled={recording}>
                ▶ Слушать {both ? 'вместе' : take ? take.name.toLowerCase() : 'оригинал'}
              </button>
            )}
            {both && (
              <>
                <div className="segmented" role="radiogroup" aria-label="Что слышно">
                  <button className={st.mix === 0 ? 'on' : ''} onClick={() => recorder.setMix(0)} title="Только оригинал (А)">
                    А · Оригинал
                  </button>
                  <button className={st.mix > 0 && st.mix < 1 ? 'on' : ''} onClick={() => recorder.setMix(0.5)}>
                    Вместе
                  </button>
                  <button className={st.mix === 1 ? 'on' : ''} onClick={() => recorder.setMix(1)} title="Только я (Б)">
                    Б · Я
                  </button>
                </div>
                <label className="slider rec-mix">
                  <span>Оригинал ↔ Я</span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={st.mix}
                    onChange={(e) => recorder.setMix(Number(e.target.value))}
                  />
                </label>
                <label className="slider rec-mix" title="Если дубль чуть отстаёт или спешит относительно оригинала — подвиньте">
                  <span>Сдвиг дубля: {Math.round(((take.refAt ?? 0) - (take.refAt0 ?? 0)) * 1000)} мс</span>
                  <input
                    type="range"
                    min={(take.refAt0 ?? 0) - 0.3}
                    max={(take.refAt0 ?? 0) + 0.3}
                    step={0.005}
                    value={take.refAt ?? 0}
                    onChange={(e) => recorder.shift(take.id, Number(e.target.value))}
                  />
                </label>
              </>
            )}
          </div>
        </div>
      )}

      {st.takes.length > 0 && (
        <div className="rec-takes">
          {st.takes.map((t) => (
            <div key={t.id} className={`rec-take ${t.id === take?.id ? 'on' : ''}`}>
              <button className="link" onClick={() => setSelected(t.id)} title="Показать и сравнить">
                {t.name}
              </button>
              <small>
                {fmt(t.samples.length / t.sampleRate)}
                {t.refAt != null && ` · с ${fmt(Math.max(0, t.refAt))} оригинала`}
              </small>
              <button
                className="btn small"
                onClick={() =>
                  playingTake === t.id
                    ? recorder.stop()
                    : (setSelected(t.id), recorder.play(t.id, t.refAt != null && st.reference ? Math.max(0, t.refAt) : 0))
                }
              >
                {playingTake === t.id ? '■' : '▶'}
              </button>
              <button className="btn small" onClick={() => save(t)} title="Сохранить файл WAV (24 бит, без потерь)">
                💾 WAV
              </button>
              <button className="btn small" onClick={() => recorder.remove(t.id)} title="Удалить дубль">
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const recordModule: ModuleDef = {
  id: 'record',
  title: 'Запись',
  icon: '⏺',
  group: 'tools',
  description: 'Записать себя, послушать и сравнить с оригиналом, сохранить WAV',
  keywords: ['запись', 'дубль', 'сравнить', 'wav', 'записать'],
  View: RecordView,
};
