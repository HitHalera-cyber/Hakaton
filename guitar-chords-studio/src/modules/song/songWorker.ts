// Анализ песни в отдельном потоке, чтобы интерфейс не «замирал» на длинных файлах.
import { extractFeatures } from '../../core/analysis/songAnalysis';

interface Request {
  samples: Float32Array;
  sampleRate: number;
}

const ctx = self as unknown as {
  postMessage(msg: unknown): void;
  onmessage: ((e: MessageEvent<Request>) => void) | null;
};

ctx.onmessage = (e) => {
  try {
    const features = extractFeatures(e.data.samples, e.data.sampleRate, (p) => ctx.postMessage({ type: 'progress', p }));
    ctx.postMessage({ type: 'done', features });
  } catch (err) {
    ctx.postMessage({ type: 'error', message: err instanceof Error ? err.message : String(err) });
  }
};
