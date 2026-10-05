// Идентификаторы модулей (разделов). Отдельный файл без импортов — его читают и хранилище, и оболочка.

export const MODULE_IDS = [
  'sound',
  'sequence',
  'metronome',
  'songbook',
  'song',
  'listen',
  'circle',
  'melody',
  'lessons',
  'changes',
  'rhythm',
  'fingercheck',
  'trainer',
  'stats',
  'library',
  'scales',
  'key',
  'tuner',
  'record',
  'midi',
  'favorites',
] as const;

export type ModuleId = (typeof MODULE_IDS)[number];

export const isModuleId = (x: unknown): x is ModuleId => typeof x === 'string' && (MODULE_IDS as readonly string[]).includes(x);
