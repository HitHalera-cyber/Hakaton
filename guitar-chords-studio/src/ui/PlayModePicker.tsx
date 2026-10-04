import { audio, type PlayMode } from '../core/audio/engine';
import { store, usePick } from '../store';

const PLAY_MODES: [PlayMode, string, string][] = [
  ['strum', '↓ Бой', 'Бой вниз: удар по струнам от баса к тонким'],
  ['strumUp', '↑ Бой', 'Бой вверх: удар от тонких струн к басу'],
  ['arpeggio', '♪ Перебор', 'Перебор: струны по одной'],
];

/** Как звучит аккорд (кнопка «Играть», автоигра): бой вниз, бой вверх, перебор. Выбор запоминается. */
export function PlayModePicker() {
  const { mode, arpStepMs, patch } = usePick((s) => ({
    mode: s.settings.sound.mode,
    arpStepMs: s.settings.sound.arpStepMs,
    patch: s.patchSound,
  }));
  return (
    <div
      className="segmented play-mode"
      role="radiogroup"
      aria-label="Как звучит аккорд"
      title="Как программа играет аккорд — для кнопки «Играть» и автоигры"
    >
      {PLAY_MODES.map(([m, label, title]) => (
        <button
          key={m}
          className={mode === m ? 'on' : ''}
          title={title}
          onClick={() => {
            patch({ mode: m });
            const notes = store.getState().currentNotes();
            if (notes.length) audio.playChord(notes, m, arpStepMs);
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
