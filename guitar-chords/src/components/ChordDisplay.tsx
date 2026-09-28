import type { DetectionResult } from '../music/chords';
import { midiName, pcName, pcNameRu, spelledName } from '../music/notes';

interface Props {
  result: DetectionResult;
  soundingMidi: number[];
  source: 'board' | 'midi';
  onPlay: () => void;
  onSave: () => void;
  canSave: boolean;
}

export function ChordDisplay({ result, soundingMidi, source, onPlay, onSave, canSave }: Props) {
  const p = result.primary;
  let symbol = '—';
  let ru = 'Поставьте точки на грифе или сыграйте аккорд на MIDI-клавиатуре';
  let unknown = false;

  switch (result.kind) {
    case 'chord':
      symbol = p!.symbol;
      ru = p!.nameRu + (p!.inversionRu ? `, ${p!.inversionRu}` : '');
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

  // Ступени для подписи состава аккорда.
  const tones =
    result.kind === 'chord' && p
      ? p.notes.map((n, i) => ({ name: spelledName(n), degree: DEGREE_NAMES[p.degrees[i]] ?? p.degrees[i] }))
      : result.noteNames.map((name) => ({ name, degree: '' }));

  return (
    <section className="panel chord-panel">
      <div className="chord-head">
        <div className="chord-main">
          <div className="chord-source">{source === 'midi' ? 'С MIDI-клавиатуры' : 'С грифа'}</div>
          <div className={`chord-symbol ${unknown ? 'unknown' : ''}`}>{symbol}</div>
          <div className="chord-ru">{ru}</div>
        </div>
        <div className="chord-actions">
          <button className="btn primary big" onClick={onPlay} disabled={soundingMidi.length === 0} title="Пробел">
            ▶ Играть
          </button>
          <button className="btn" onClick={onSave} disabled={!canSave} title="Сохранить аппликатуру в избранное">
            ★ Сохранить
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

      {soundingMidi.length > 0 && (
        <div className="chord-sounding">
          <span className="muted-label">Звучат:</span> {soundingMidi.map(midiName).join(' ')}
        </div>
      )}

      {result.alternatives.length > 0 && (
        <div className="chord-alts">
          <span className="muted-label">{unknown || result.kind === 'interval' ? 'Ближайшие варианты:' : 'Другие трактовки:'}</span>
          {result.alternatives.map((a) => (
            <span key={a.symbol} className={`alt ${a.exact ? '' : 'approx'}`} title={a.nameRu + (a.inversionRu ? `, ${a.inversionRu}` : '')}>
              {a.symbol}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

const DEGREE_NAMES: Record<string, string> = { '1': 'тоника', '+': 'доб.' };
