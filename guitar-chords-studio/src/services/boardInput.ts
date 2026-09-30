// Перехват кликов по грифу: тренажёр и уроки проверяют ответ вместо того, чтобы ставить точку.

type CellHandler = (s: number, f: number) => boolean;

let handler: CellHandler | null = null;
const listeners = new Set<() => void>();

export const boardInput = {
  get handler() {
    return handler;
  },
  register(fn: CellHandler | null) {
    handler = fn;
    listeners.forEach((l) => l());
  },
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
