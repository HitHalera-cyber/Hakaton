// WAV без сжатия: моно, 16 или 24 бита. Такой файл открывается любой программой и не теряет качества.

export function encodeWav(samples: Float32Array, sampleRate: number, bits: 16 | 24 = 24): ArrayBuffer {
  const bytes = bits / 8;
  const dataSize = samples.length * bytes;
  const buf = new ArrayBuffer(44 + dataSize);
  const v = new DataView(buf);
  const text = (o: number, s: string) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)));
  text(0, 'RIFF');
  v.setUint32(4, 36 + dataSize, true);
  text(8, 'WAVE');
  text(12, 'fmt ');
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // моно
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * bytes, true);
  v.setUint16(32, bytes, true);
  v.setUint16(34, bits, true);
  text(36, 'data');
  v.setUint32(40, dataSize, true);
  const max = 2 ** (bits - 1) - 1;
  let o = 44;
  for (let i = 0; i < samples.length; i++) {
    const x = Math.round(Math.max(-1, Math.min(1, samples[i])) * max);
    if (bits === 16) v.setInt16(o, x, true);
    else {
      v.setUint8(o, x & 0xff);
      v.setUint8(o + 1, (x >> 8) & 0xff);
      v.setUint8(o + 2, (x >> 16) & 0xff);
    }
    o += bytes;
  }
  return buf;
}

/** Прочитать моно WAV (для проверки). */
export function decodeWav(buf: ArrayBuffer): { samples: Float32Array; sampleRate: number; bits: number } {
  const v = new DataView(buf);
  const sampleRate = v.getUint32(24, true);
  const bits = v.getUint16(34, true);
  const bytes = bits / 8;
  const n = v.getUint32(40, true) / bytes;
  const max = 2 ** (bits - 1) - 1;
  const samples = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const o = 44 + i * bytes;
    let x: number;
    if (bits === 16) x = v.getInt16(o, true);
    else {
      x = v.getUint8(o) | (v.getUint8(o + 1) << 8) | (v.getUint8(o + 2) << 16);
      if (x & 0x800000) x -= 0x1000000;
    }
    samples[i] = x / max;
  }
  return { samples, sampleRate, bits };
}
