import './song.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { audio as engine } from '../../core/audio/engine';
import { saveFile, safeName } from '../../core/export/download';
import { SONG_VOCAB } from '../../core/analysis/chordRecognition';
import { parseChordSymbol } from '../../core/music/chordParse';
import { keyRootSpelling } from '../../core/music/scales';
import { spelledName } from '../../core/music/notes';
import { FX_NAMES, setSongFx, type SongFxMode } from './songFx';
import { decodeChords, detectKey, shapeName, suggestCapo, type ChordSegment, type SongFeatures } from '../../core/analysis/songAnalysis';

export interface SongChord {
  rootPc: number;
  templateId: string;
  bassPc?: number;
  symbol: string;
  beats: number;
}

interface Props {
  capo: number;
  onCapo: (c: number) => void;
  /** Показать аккорд на грифе (без звука — играет песня). */
  onChord: (c: SongChord) => void;
  onToSequence: (chords: SongChord[]) => void;
  /** Перенести аккорды разбора в песенник (по тактам). */
  onToSongbook: (chords: SongChord[], info: { title: string; bpm: number; capo: number }) => void;
  onToast: (text: string) => void;
  /** Сообщает, играет ли песня (чтобы микрофон в это время не менял гриф). */
  onPlayingChange?: (playing: boolean) => void;
  /** Панель открыта/закрыта: пока она открыта, гриф показывает только аккорды песни. */
  onOpenChange?: (open: boolean) => void;
}

type Status = 'idle' | 'decoding' | 'analyzing' | 'ready' | 'error';

const fmt = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
const PX_PER_SEC = 34;

export function SongPanel({ capo, onCapo, onChord, onToSequence, onToSongbook, onToast, onPlayingChange, onOpenChange }: Props) {
  const [status, setStatus] = useState<Status>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');
  const [features, setFeatures] = useState<SongFeatures | null>(null);
  const [vocab, setVocab] = useState<keyof typeof SONG_VOCAB>('simple');
  /** Минимальная длина аккорда в долях: защита от «дёрганья» из-за шума. */
  const [stability, setStability] = useState(2);
  const [edits, setEdits] = useState<Record<number, { rootPc: number; templateId: string; symbol: string; nameRu: string }>>({});
  const [url, setUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [follow, setFollow] = useState(true);
  const [volume, setVolume] = useState(0.9);
  /** Скорость воспроизведения без изменения высоты (0,5–1). */
  const [rate, setRate] = useState(1);
  /** Повтор куска A–B. */
  const [loop, setLoop] = useState<{ a: number | null; b: number | null }>({ a: null, b: null });
  const [fx, setFx] = useState<SongFxMode>('original');
  /** Звук песни уже идёт через обработку (подключить можно только один раз). */
  const graphConnected = useRef(false);
  const loopRef = useRef(loop);
  loopRef.current = loop;
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [drag, setDrag] = useState(false);
  const player = useRef<HTMLAudioElement | null>(null);
  const timeline = useRef<HTMLDivElement | null>(null);
  const worker = useRef<Worker | null>(null);
  const lastIdx = useRef(-1);

  useEffect(
    () => () => {
      worker.current?.terminate();
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );

  // Сегменты с учётом ручных исправлений (ключ — время начала в миллисекундах).
  const segments: ChordSegment[] = useMemo(() => {
    if (!features) return [];
    return decodeChords(features, SONG_VOCAB[vocab], stability).map((s) => {
      const e = edits[Math.round(s.start * 1000)];
      return e ? { ...s, ...e } : s;
    });
  }, [features, vocab, stability, edits]);
  const key = useMemo(() => (features ? detectKey(features) : null), [features]);
  const capoOptions = useMemo(() => suggestCapo(segments).slice(0, 3), [segments]);
  const current = segments.findIndex((s) => time >= s.start && time < s.end);

  // Показ текущего аккорда на грифе и прокрутка ленты.
  useEffect(() => {
    if (current < 0 || current === lastIdx.current) return;
    lastIdx.current = current;
    const s = segments[current];
    if (follow && s.rootPc != null && s.templateId)
      onChord({ rootPc: s.rootPc, templateId: s.templateId, symbol: s.symbol, beats: s.beats });
    const el = timeline.current?.querySelector<HTMLElement>(`[data-i="${current}"]`);
    el?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
  }, [current, segments, follow, onChord]);

  useEffect(() => {
    if (player.current) player.current.volume = volume;
  }, [volume, url]);
  useEffect(() => {
    const p = player.current;
    if (!p) return;
    p.preservesPitch = true;
    p.playbackRate = rate;
  }, [rate, url]);
  useEffect(() => {
    if (player.current && (fx !== 'original' || graphConnected.current)) {
      graphConnected.current = true;
      setSongFx(player.current, fx);
    }
  }, [fx, url]);

  useEffect(() => {
    onPlayingChange?.(playing);
  }, [playing, onPlayingChange]);
  useEffect(() => () => onPlayingChange?.(false), [onPlayingChange]);
  useEffect(() => {
    onOpenChange?.(true);
    return () => onOpenChange?.(false);
  }, [onOpenChange]);

  // Плавное обновление позиции при воспроизведении.
  useEffect(() => {
    if (!playing) return;
    let id = 0;
    const tick = () => {
      const p = player.current;
      if (p) {
        const { a, b } = loopRef.current;
        // Повтор куска: дошли до B — назад в A.
        if (a != null && b != null && b > a && p.currentTime >= b) p.currentTime = a;
        setTime(p.currentTime);
      }
      id = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(id);
  }, [playing]);

  const load = async (file: File) => {
    setError('');
    setFeatures(null);
    setEdits({});
    setPlaying(false);
    setTime(0);
    setLoop({ a: null, b: null });
    setFx('original');
    lastIdx.current = -1;
    setFileName(file.name);
    setStatus('decoding');
    setProgress(0);
    try {
      const data = await file.arrayBuffer();
      if (url) URL.revokeObjectURL(url);
      setUrl(URL.createObjectURL(file));
      const buffer = await engine.context.decodeAudioData(data.slice(0));
      // Моно: среднее каналов.
      const mono = new Float32Array(buffer.length);
      for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
        const d = buffer.getChannelData(ch);
        for (let i = 0; i < d.length; i++) mono[i] += d[i] / buffer.numberOfChannels;
      }
      setStatus('analyzing');
      worker.current?.terminate();
      const w = new Worker(new URL('./songWorker.ts', import.meta.url), { type: 'module' });
      worker.current = w;
      w.onmessage = (e: MessageEvent) => {
        const msg = e.data;
        if (msg.type === 'progress') setProgress(msg.p);
        else if (msg.type === 'done') {
          setFeatures(msg.features);
          setStatus('ready');
          w.terminate();
        } else if (msg.type === 'error') {
          setError(msg.message);
          setStatus('error');
        }
      };
      w.postMessage({ samples: mono, sampleRate: buffer.sampleRate }, [mono.buffer]);
    } catch {
      setStatus('error');
      setError('Не удалось прочитать файл. Поддерживаются MP3, WAV, OGG, FLAC, M4A/AAC.');
    }
  };

  const pick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'audio/*,.mp3,.wav,.ogg,.flac,.m4a,.aac';
    input.onchange = () => input.files?.[0] && void load(input.files[0]);
    input.click();
  };

  const seek = (t: number) => {
    if (!player.current) return;
    player.current.currentTime = t;
    setTime(t);
  };

  const togglePlay = () => {
    const p = player.current;
    if (!p) return;
    if (p.paused) {
      engine.stopAll();
      void p.play();
      setPlaying(true);
    } else {
      p.pause();
      setPlaying(false);
    }
  };

  const applyEdit = (i: number) => {
    const parsed = parseChordSymbol(draft);
    if (!parsed) {
      onToast('Не понял аккорд. Примеры: Am, G7, F#m');
      return;
    }
    const s = segments[i];
    setEdits((e) => ({
      ...e,
      [Math.round(s.start * 1000)]: { rootPc: parsed.rootPc, templateId: parsed.template.id, symbol: parsed.symbol, nameRu: parsed.nameRu },
    }));
    setEditing(null);
  };

  const chordList = segments.filter((s) => s.rootPc != null);
  const unique = [...new Map(chordList.map((s) => [s.symbol, s])).values()];
  const keyName = key ? `${spelledName(keyRootSpelling(key.tonicPc, key.mode))} ${key.mode === 'major' ? 'мажор' : 'минор'}` : '';

  const exportText = () => {
    const lines = [
      `${fileName}`,
      `Тональность: ${keyName} · темп ≈ ${features?.bpm} уд/мин${capo ? ` · каподастр: ${capo} лад (аккорды — формы)` : ''}`,
      '',
      ...chordList.map((s) => `${fmt(s.start)}  ${capo ? shapeName(s, capo) : s.symbol}${capo ? `  (звучит ${s.symbol})` : ''}`),
    ];
    saveFile(lines.join('\n'), `${safeName(fileName.replace(/\.[^.]+$/, ''))} — аккорды.txt`, 'text/plain;charset=utf-8');
  };

  return (
    <div
      className={`tab-body song ${drag ? 'drag' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) void load(f);
      }}
    >
      {status === 'idle' || status === 'error' ? (
        <div className="dropzone" onClick={pick}>
          <b>🎧 Перетащите сюда файл с песней</b>
          <span>или нажмите, чтобы выбрать · MP3, WAV, OGG, FLAC, M4A</span>
        </div>
      ) : (
        <div className="row between">
          <span className="song-name" title={fileName}>
            🎵 {fileName}
          </span>
          <button className="btn small" onClick={pick}>
            Другой файл
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {(status === 'decoding' || status === 'analyzing') && (
        <div className="progress">
          <span style={{ width: `${Math.round((status === 'decoding' ? 0.05 : 0.05 + progress * 0.95) * 100)}%` }} />
          <small>{status === 'decoding' ? 'Читаю файл…' : `Слушаю песню… ${Math.round(progress * 100)}%`}</small>
        </div>
      )}

      {url && (
        <audio ref={player} src={url} onEnded={() => setPlaying(false)} onPause={() => setPlaying(false)} style={{ display: 'none' }} />
      )}

      {status === 'ready' && features && (
        <>
          <div className="song-info">
            <span>
              Тональность: <b>{keyName}</b>
            </span>
            <span>
              Темп: <b>≈ {features.bpm}</b> уд/мин
            </span>
            <span>
              Длительность: <b>{fmt(features.duration)}</b>
            </span>
            {Math.abs(features.tuningCents ?? 0) >= 5 && (
              <span title="Запись настроена не точно на A = 440 Гц — программа это учитывает">
                Строй записи:{' '}
                <b>
                  {features.tuningCents > 0 ? '+' : ''}
                  {features.tuningCents} ц
                </b>
              </span>
            )}
          </div>

          <div className="row">
            <label className="field inline">
              <span>Аккорды</span>
              <select value={vocab} onChange={(e) => setVocab(e.target.value as keyof typeof SONG_VOCAB)}>
                <option value="simple">Простые (мажор / минор) — точнее</option>
                <option value="sevenths">С септаккордами</option>
              </select>
            </label>
            <label className="field inline" title="Короткие «вспышки» аккордов (шум, вокал, проходящие ноты) убираются">
              <span>Стабильность</span>
              <select value={stability} onChange={(e) => setStability(Number(e.target.value))}>
                <option value={1}>низкая — каждая доля</option>
                <option value={2}>средняя — от 2 долей</option>
                <option value={3}>высокая — почти такт</option>
              </select>
            </label>
            <label className="field inline" title="С каподастром песню можно играть простыми формами аккордов">
              <span>Каподастр</span>
              <select value={capo} onChange={(e) => onCapo(Number(e.target.value))}>
                {Array.from({ length: 8 }, (_, c) => {
                  const opt = capoOptions.find((o) => o.capo === c);
                  return (
                    <option key={c} value={c}>
                      {c === 0 ? 'нет' : `${c} лад`}
                      {opt && opt === capoOptions[0] ? ' — рекомендую' : ''}
                    </option>
                  );
                })}
              </select>
            </label>
            {capoOptions[0] && capoOptions[0].capo !== capo && (
              <button className="btn small" onClick={() => onCapo(capoOptions[0].capo)}>
                Каподастр на {capoOptions[0].capo || 'нет'} — {Math.round(capoOptions[0].easyShare * 100)}% простых аккордов
              </button>
            )}
          </div>

          <div className="player">
            <button className="btn primary round" onClick={togglePlay} title="Играть / пауза">
              {playing ? '❚❚' : '▶'}
            </button>
            <span className="time">
              {fmt(time)} / {fmt(features.duration)}
            </span>
            <input
              className="grow"
              type="range"
              min={0}
              max={features.duration}
              step={0.1}
              value={time}
              onChange={(e) => seek(Number(e.target.value))}
            />
            <label className="slider vol" title="Громкость песни">
              <input type="range" min={0} max={1} step={0.01} value={volume} onChange={(e) => setVolume(Number(e.target.value))} />
            </label>
          </div>

          <div className="practice-tools">
            <label className="field inline" title="Замедление без изменения высоты звука">
              <span>Скорость</span>
              <input type="range" min={0.5} max={1} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
              <b className="rate">{Math.round(rate * 100)}%</b>
            </label>
            <div className="ab" title="Повтор куска: поставьте начало (A) и конец (B)">
              <span>Повтор</span>
              <button
                className={`btn small ${loop.a != null ? 'on' : ''}`}
                onClick={() => setLoop((l) => ({ a: time, b: l.b != null && l.b > time ? l.b : null }))}
              >
                A {loop.a != null ? fmt(loop.a) : ''}
              </button>
              <button
                className={`btn small ${loop.b != null ? 'on' : ''}`}
                disabled={loop.a == null}
                onClick={() => loop.a != null && time > loop.a && setLoop((l) => ({ ...l, b: time }))}
              >
                B {loop.b != null ? fmt(loop.b) : ''}
              </button>
              {(loop.a != null || loop.b != null) && (
                <button className="btn small" onClick={() => setLoop({ a: null, b: null })} title="Убрать повтор">
                  ✕
                </button>
              )}
            </div>
            <div
              className="segmented"
              role="radiogroup"
              aria-label="Обработка звука"
              title="Вокал обычно по центру стерео — его можно приглушить"
            >
              {(Object.keys(FX_NAMES) as SongFxMode[]).map((m) => (
                <button key={m} className={fx === m ? 'on' : ''} onClick={() => setFx(m)}>
                  {FX_NAMES[m]}
                </button>
              ))}
            </div>
          </div>

          <div className="now-playing">
            {current >= 0 && segments[current].rootPc != null ? (
              <>
                <span className="np-symbol">{capo ? shapeName(segments[current], capo) : segments[current].symbol}</span>
                <span className="np-ru">
                  {segments[current].nameRu}
                  {capo ? ` · звучит ${segments[current].symbol}` : ''}
                </span>
                {segments[current + 1]?.rootPc != null && (
                  <span className="np-next">
                    дальше: <b>{capo ? shapeName(segments[current + 1], capo) : segments[current + 1].symbol}</b>
                  </span>
                )}
              </>
            ) : (
              <span className="hint">
                {current >= 0 ? 'Без аккорда' : 'Нажмите ▶ — аккорды будут подсвечиваться и показываться на грифе'}
              </span>
            )}
          </div>

          <div className="song-timeline" ref={timeline}>
            <div className="st-inner" style={{ width: features.duration * PX_PER_SEC }}>
              {segments.map((s, i) => (
                <button
                  key={i}
                  data-i={i}
                  className={`st-seg ${s.rootPc == null ? 'none' : ''} ${i === current ? 'on' : ''} ${edits[Math.round(s.start * 1000)] ? 'edited' : ''}`}
                  style={{ left: s.start * PX_PER_SEC, width: Math.max(2, (s.end - s.start) * PX_PER_SEC - 2) }}
                  onClick={() => seek(s.start + 0.01)}
                  onDoubleClick={() => {
                    setEditing(i);
                    setDraft(s.rootPc == null ? '' : s.symbol);
                  }}
                  title={`${fmt(s.start)} · ${s.nameRu} · двойной клик — исправить`}
                >
                  {s.rootPc == null ? '' : capo ? shapeName(s, capo) : s.symbol}
                </button>
              ))}
              <span className="st-cursor" style={{ left: time * PX_PER_SEC }} />
            </div>
          </div>

          {editing != null && (
            <div className="row edit-row">
              <span>Исправить аккорд на {fmt(segments[editing].start)} (звучащий, без учёта каподастра):</span>
              <input
                autoFocus
                className="text-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === 'Enter') applyEdit(editing);
                  if (e.key === 'Escape') setEditing(null);
                }}
                placeholder="например, Am"
              />
              <button className="btn small primary" onClick={() => applyEdit(editing)}>
                OK
              </button>
              <button className="btn small" onClick={() => setEditing(null)}>
                Отмена
              </button>
            </div>
          )}

          <div className="song-chords">
            <span className="muted-label">Аккорды песни{capo ? ` (формы с каподастром на ${capo} ладу)` : ''}:</span>
            {unique.map((s) => (
              <button
                key={s.symbol}
                className="alt"
                onClick={() => onChord({ rootPc: s.rootPc!, templateId: s.templateId!, symbol: s.symbol, beats: s.beats })}
                title={`${s.nameRu} — показать на грифе`}
              >
                {capo ? shapeName(s, capo) : s.symbol}
              </button>
            ))}
          </div>

          <div className="row">
            <label className="check">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
              Показывать текущий аккорд на грифе
            </label>
            <span className="hint" title="Микрофон и «Слушать аккорд» не меняют гриф, пока открыт разбор песни">
              🔇 гриф — только аккорды песни
            </span>
            <span className="grow" />
            <button
              className="btn small"
              onClick={() =>
                onToSequence(
                  chordList.map((s) => ({ rootPc: s.rootPc!, templateId: s.templateId!, symbol: s.symbol, beats: Math.min(8, s.beats) })),
                )
              }
            >
              → В последовательность
            </button>
            <button
              className="btn small"
              onClick={() =>
                onToSongbook(
                  chordList.map((s) => ({ rootPc: s.rootPc!, templateId: s.templateId!, symbol: s.symbol, beats: s.beats })),
                  { title: fileName.replace(/\.[^.]+$/, ''), bpm: features?.bpm ?? 90, capo },
                )
              }
              title="Создать песню в песеннике: аккорды по тактам"
            >
              → В песенник
            </button>
            <button className="btn small" onClick={exportText}>
              ⇩ Аккорды (.txt)
            </button>
          </div>
          <p className="hint">
            Разбор автоматический и может ошибаться (особенно в песнях с сильной обработкой, речитативом или без чётких аккордов). Двойной
            клик по аккорду на ленте — исправить. Режим «Простые» надёжнее, чем «С септаккордами».
          </p>
        </>
      )}
    </div>
  );
}
