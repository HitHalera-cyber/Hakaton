import { TUNINGS } from '../../src/music/tunings';

export const SR = 48000;
const STD = TUNINGS.standard.strings;

/**
 * Звук струны для тестов: сумма гармоник с гитарным спектром (амплитуды спадают как 1/h,
 * у низких струн основной тон ослаблен, как в записи), с затуханием. Детерминирован.
 */
export function stringTone(midi: number, seconds: number, bright = 1): Float32Array {
  const f0 = 440 * Math.pow(2, (midi - 69) / 12);
  const out = new Float32Array(Math.floor(SR * seconds));
  const fundamental = midi < 50 ? 0.35 : midi < 57 ? 0.7 : 1;
  for (let h = 1; h <= 10; h++) {
    const f = f0 * h * (1 + 0.0002 * h * h); // лёгкая негармоничность струны
    if (f > SR / 2) break;
    const amp = (h === 1 ? fundamental : 1 / Math.pow(h, 1.2 / bright)) * 0.2;
    const decay = 1.5 + h * 0.8;
    for (let i = 0; i < out.length; i++) out[i] += amp * Math.exp((-decay * i) / SR) * Math.sin((2 * Math.PI * f * i) / SR + h);
  }
  return out;
}

/** Аккорд в табулатурной записи 'x32010', бой сверху вниз. */
export function strum(tab: string, bright = 1, seconds = 1.2): Float32Array {
  const out = new Float32Array(Math.floor(SR * seconds));
  [...tab].forEach((ch, s) => {
    if (ch === 'x') return;
    const note = stringTone(STD[s] + parseInt(ch, 16), seconds, bright);
    const offset = Math.floor(s * 0.015 * SR);
    for (let i = 0; i + offset < out.length; i++) out[i + offset] += note[i];
  });
  return out;
}
