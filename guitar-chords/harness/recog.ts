import { LIVE_VOCAB, buildModels, recognizeChord } from '../src/music/chordRecognition';
import { SpectrumAnalyzer, detectNotes } from '../src/music/dsp';
const STD = [40, 45, 50, 55, 59, 64];
const N = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
const cases: [string, string][] = [
  ['x32010', 'C'], ['x02210', 'Am'], ['320003', 'G'], ['022100', 'E'], ['xx0232', 'D'], ['133211', 'F'],
  ['022030', 'Em7'], ['320001', 'G7'], ['xx0233', 'Dsus4'], ['x32000', 'Cmaj7'], ['xx0231', 'Dm'], ['022000', 'Em'],
  ['x02020', 'A7'], ['x24432', 'Bm'], ['244222', 'F#m'], ['x35553', 'C'], ['032010', 'C/E'], ['x02220', 'A'], ['x13331', 'Bb'], ['xx0212', 'D7'],
];
(window as any).run = async (set: string) => {
  const ctx = new OfflineAudioContext(1, 48000, 48000);
  const cache = new Map<number, AudioBuffer>();
  const load = async (m: number) => {
    if (!cache.has(m)) cache.set(m, await ctx.decodeAudioData(await (await fetch(`/samples/${set}/${m}.mp3`)).arrayBuffer()));
    return cache.get(m)!;
  };
  const SR = 48000;
  const an = new SpectrumAnalyzer(16384, SR);
  const models = buildModels(LIVE_VOCAB);
  const out: string[] = [];
  let ok = 0;
  for (const [tab, want] of cases) {
    const x = new Float32Array(SR * 1.2);
    let s = 0;
    for (const ch of tab) {
      if (ch !== 'x') {
        const buf = await load(STD[s] + parseInt(ch, 16));
        const d = buf.getChannelData(0);
        const off = Math.floor(s * 0.015 * SR);
        const ratio = buf.sampleRate / SR;
        for (let i = 0; i + off < x.length; i++) { const j = Math.floor(i * ratio); if (j >= d.length) break; x[i + off] += d[j] * 0.8; }
      }
      s++;
    }
    const chroma = new Float32Array(12), bass = new Float32Array(12);
    let notesDbg = '';
    for (const st of [0.12, 0.2, 0.28]) {
      const f = an.frame(x, Math.floor(st * SR));
      for (let i = 0; i < 12; i++) { chroma[i] += f.chroma[i]; bass[i] += f.bass[i]; }
      if (st === 0.2) notesDbg = detectNotes(an.semitones(x, Math.floor(st * SR)).semi).map(n => N[n.midi % 12] + (Math.floor(n.midi / 12) - 1)).join(' ') + ' | bass ' + [...bass].map((v,i)=>[v,i]).sort((a,b)=>b[0]-a[0]).slice(0,2).map(([v,i])=>N[i]+':'+v.toFixed(2)).join(' ');
    }
    const r = recognizeChord(chroma, bass, models);
    const got = r.best?.symbol;
    if (got === want) ok++;
    out.push(`${got === want ? 'ok ' : 'BAD'} ${tab} want ${want} got ${got} (${Math.round((r.best?.confidence ?? 0) * 100)}%) notes: ${notesDbg}`);
  }
  return `${set}: ${ok}/${cases.length}\n` + out.join('\n');
};

// ---------- Генерация тестовых WAV из записанных сэмплов ----------
function wav(x: Float32Array, sr: number): string {
  const buf = new ArrayBuffer(44 + x.length * 2);
  const v = new DataView(buf);
  const w = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); v.setUint32(4, 36 + x.length * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, sr, true);
  v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, x.length * 2, true);
  for (let i = 0; i < x.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, x[i])) * 32767, true);
  let bin = '';
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(bin);
}

(window as any).render = async (kind: 'song' | 'live') => {
  const SR = 48000;
  const ctx = new OfflineAudioContext(1, SR, SR);
  const cache = new Map<string, Float32Array>();
  const load = async (set: string, m: number) => {
    const k = set + m;
    if (!cache.has(k)) {
      const b = await ctx.decodeAudioData(await (await fetch(`/samples/${set}/${m}.mp3`)).arrayBuffer());
      const d = b.getChannelData(0);
      const r = b.sampleRate / SR;
      const out = new Float32Array(Math.floor(d.length / r));
      for (let i = 0; i < out.length; i++) out[i] = d[Math.floor(i * r)];
      cache.set(k, out);
    }
    return cache.get(k)!;
  };
  const add = (x: Float32Array, src: Float32Array, at: number, gain: number, maxLen = Infinity) => {
    for (let i = 0; i < src.length && i < maxLen && at + i < x.length; i++) x[at + i] += src[i] * gain * (i > maxLen - 2400 ? (maxLen - i) / 2400 : 1);
  };
  const strumAt = async (x: Float32Array, tab: string, at: number, gain: number, maxLen: number, up = false) => {
    const strings = [...tab].map((c, s) => (c === 'x' ? null : STD[s] + parseInt(c, 16)));
    const order = up ? [...strings.keys()].reverse() : [...strings.keys()];
    let k = 0;
    for (const s of order) {
      const m = strings[s];
      if (m == null) continue;
      add(x, await load('steel', m), at + Math.floor(k++ * 0.014 * SR), gain, maxLen);
    }
  };
  if (kind === 'live') {
    // Удары аккордов с паузами — как будто играют в микрофон.
    const seq = ['x32010', 'x02210', '320003', '022000', 'xx0232', '133211'];
    const x = new Float32Array(SR * (2 + seq.length * 2.5));
    for (let i = 0; i < seq.length; i++) await strumAt(x, seq[i], Math.floor((1 + i * 2.5) * SR), 0.5, SR * 2.2);
    for (let i = 0; i < x.length; i++) x[i] += (Math.random() - 0.5) * 0.002; // лёгкий шум комнаты
    return wav(x, SR);
  }
  // «Песня»: Am F C G по такту, 100 уд/мин, бой ↓ ↓↑ ↑↓↑, бас и бочка.
  const bpm = 100, beat = 60 / bpm;
  const prog: [string, number][] = [['x02210', 45], ['133211', 41], ['x32010', 48], ['320003', 43]];
  const bars = 16;
  const x = new Float32Array(Math.floor((bars * 4 * beat + 2) * SR));
  for (let bar = 0; bar < bars; bar++) {
    const [tab, bassNote] = prog[bar % 4];
    const t0 = 0.5 + bar * 4 * beat;
    const pattern: [number, boolean][] = [[0, false], [1, false], [1.5, true], [2.5, true], [3, false], [3.5, true]];
    for (const [pos, up] of pattern) await strumAt(x, tab, Math.floor((t0 + pos * beat) * SR), up ? 0.25 : 0.35, Math.floor(beat * SR * 1.2), up);
    for (let b = 0; b < 4; b++) {
      const at = Math.floor((t0 + b * beat) * SR);
      add(x, await load('bass', bassNote - 12), at, 0.6, Math.floor(beat * SR));
      for (let i = 0; i < SR * 0.12; i++) x[at + i] += 0.45 * Math.sin(2 * Math.PI * 60 * i / SR * (1 - i / SR * 2)) * Math.exp(-30 * i / SR);
      for (let i = 0; i < SR * 0.05; i++) x[at + Math.floor(beat * SR / 2) + i] += 0.05 * (Math.random() - 0.5) * Math.exp(-80 * i / SR);
    }
  }
  let peak = 0;
  for (const v of x) peak = Math.max(peak, Math.abs(v));
  for (let i = 0; i < x.length; i++) x[i] *= 0.9 / peak;
  return wav(x, SR);
};
