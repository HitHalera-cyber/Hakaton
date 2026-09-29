// Раскладки окна: где стоят гриф, аккорд и разделы. Сами раскладки — в src/app/layout/.

import { isTab, type TabId } from './navigation';

export type LayoutId = 'classic' | 'dashboard' | 'listener' | 'free';

export const LAYOUTS: { id: LayoutId; name: string; description: string }[] = [
  { id: 'classic', name: 'Классика', description: 'Меню слева, гриф сверху, под ним аккорд и выбранный раздел' },
  { id: 'dashboard', name: 'Приборная панель', description: 'Гриф, аккорд и четыре плитки с разделами видны сразу' },
  { id: 'listener', name: 'Слушатель', description: 'Для живой игры: крупно услышанный аккорд, круг и история' },
  { id: 'free', name: 'Свободные окна', description: 'Разделы в окнах: перетаскивайте, меняйте размер, закрывайте' },
];

export const isLayout = (x: unknown): x is LayoutId => LAYOUTS.some((l) => l.id === x);

/** Плитки приборной панели по умолчанию. */
export const DEFAULT_TILES: TabId[] = ['circle', 'listen', 'sound', 'favorites'];

export function normalizeTiles(t: unknown): TabId[] {
  const list = Array.isArray(t) ? t.filter((x): x is TabId => typeof x === 'string' && isTab(x)) : [];
  return list.length === DEFAULT_TILES.length ? list : DEFAULT_TILES;
}

/** Окно в раскладке «Свободные окна». */
export type WindowKind = TabId | 'chord';

export interface FreeWindow {
  id: WindowKind;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
}

export const DEFAULT_WINDOWS: FreeWindow[] = [
  { id: 'chord', x: 12, y: 12, w: 340, h: 420, z: 1 },
  { id: 'circle', x: 364, y: 12, w: 560, h: 470, z: 2 },
  { id: 'metronome', x: 936, y: 52, w: 360, h: 330, z: 3 },
];

export function normalizeWindows(list: unknown): FreeWindow[] {
  if (!Array.isArray(list)) return DEFAULT_WINDOWS;
  return list.filter(
    (w): w is FreeWindow =>
      w && (w.id === 'chord' || isTab(w.id)) && [w.x, w.y, w.w, w.h, w.z].every((n) => typeof n === 'number' && Number.isFinite(n)),
  );
}
