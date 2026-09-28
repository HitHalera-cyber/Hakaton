import type { DetectionResult } from '../music/chords';
import { midiName, pcName, pcNameRu, spelledName } from '../music/notes';

interface Props {
  result: DetectionResult;
  soundingMidi: number[];
  source: 'board' | 'midi';
  capo: number;
  /** Как называется форма аккорда без учёта каподастра (например, «G» при звучании A). */
  shapeSymbol?: string;
  warnings: string[];
  onPlay: () => void;
  onSave: () => void;
  onAddToSequence: () => void;
  onShowVoicings?: () => void;
  onExport: (kind: 'png' | 'midi' | 'tab') => void;
}

const DEGREE_NAMES: Record<string, string> = { '1': 'тоника', '+': 'доб.' };

export function ChordDisplay(p: Props) {
  const { result } = p;
  const primary = result.primary;
  let symbol = '—';
  let ru = 'Поставьте точки на грифе, выберите аккорд в справочнике или сыграйте на MIDI-клавиатуре';
  let unknown = false;

  switch (result.kind) {
    case 'chord':
      symbol = primary!.symbol;
      ru = primary!.nameRu + (primary!.inversionRu ? `, ${primary!.inversionRu}` : '');
      break;
    case 'note':
      symbol = pcName(result.pitchClasses[0]);
      ru = `Одна нота — ${pcNameRu(result.pitchClasses[0])}`;
      break;
    case 'interval':
      symbol = result.noteNames.join(' + ');
      ru = `Интервал: ${result.intervalRu}`;
      break;
    case 'unknown':
      symbol = '?';
      ru = 'Неизвестный аккорд';
      unknown = true;
      break;
  }

  const tones =
    result.kind === 'chord' && primary
      ? primary.notes.map((n, i) => ({ name: spelledName(n), degree: DEGREE_NAMES[primary.degrees[i]] ?? primary.degrees[i] }))
      : result.noteNames.map((name) => ({ name, degree: '' }));
  const has = p.soundingMidi.length > 0;

  return (
    <section className="panel chord-panel">
      <div className="chord-head">
        <div className="chord-main">
          <div className="chord-source">{p.source === 'midi' ? 'С MIDI-клавиатуры' : 'С грифа'}</div>
          <div className={`chord-symbol ${unknown ? 'unknown' : ''}`}>{symbol}</div>
          <div className="chord-ru">{ru}</div>
          {p.capo > 0 && p.shapeSymbol && p.shapeSymbol !== symbol && (
            <div className="capo-note">
              Каподастр на {p.capo} ладу: форма <b>{p.shapeSymbol}</b>, звучит как <b>{symbol}</b>
            </div>
          )}
        </div>
        <div className="chord-actions">
          <button className="btn primary big" onClick={p.onPlay} disabled={!has} title="Пробел">
            ▶ Играть
          </button>
          <button className="btn" onClick={p.onSave} disabled={!has} title="Сохранить аппликатуру в избранное">
            ★ В избранное
          </button>
          <button className="btn" onClick={p.onAddToSequence} disabled={!has} title="Добавить в конец последовательности">
            ＋ В последовательность
          </button>
        </div>
      </div>

      {tones.length > 0 && (
        <div className="chord-tones">
          <span className="muted-label">Состав:</span>
          <span className="tones">
            {tones.map((t, i) => (
              <span key={i} className={`tone ${i === 0 && result.kind === 'chord' ? 'root' : ''}`}>
                {t.name}
                {t.degree && <small>{t.degree}</small>}
                {i < tones.length - 1 && <span className="dash">–</span>}
              </span>
            ))}
          </span>
        </div>
      )}

      {has && (
        <div className="chord-sounding">
          <span className="muted-label">Звучат:</span> {p.soundingMidi.map(midiName).join(' ')}
        </div>
      )}

      {p.warnings.length > 0 && (
        <div className="warnings">
          {p.warnings.map((w) => (
            <div key={w}>⚠ {w}</div>
          ))}
        </div>
      )}

      {result.alternatives.length > 0 && (
        <div className="chord-alts">
          <span className="muted-label">{unknown || result.kind === 'interval' ? 'Ближайшие варианты:' : 'Другие названия:'}</span>
          {result.alternatives.map((a) => (
            <span key={a.symbol} className={`alt ${a.exact ? '' : 'approx'}`} title={a.nameRu + (a.inversionRu ? `, ${a.inversionRu}` : '')}>
              {a.symbol}
            </span>
          ))}
        </div>
      )}

      <div className="row export-row">
        {p.onShowVoicings && (
          <button className="btn small" onClick={p.onShowVoicings} title="Открыть справочник с другими аппликатурами этого аккорда">
            📖 Другие аппликатуры
          </button>
        )}
        <span className="grow" />
        <span className="muted-label">Экспорт:</span>
        <button className="btn small" onClick={() => p.onExport('png')} disabled={!has} title="Картинка аккордовой диаграммы">
          PNG
        </button>
        <button className="btn small" onClick={() => p.onExport('midi')} disabled={!has} title="MIDI-файл с аккордом">
          MIDI
        </button>
        <button className="btn small" onClick={() => p.onExport('tab')} disabled={!has} title="Текстовая табулатура (копируется и сохраняется)">
          Таб
        </button>
      </div>
    </section>
  );
}
