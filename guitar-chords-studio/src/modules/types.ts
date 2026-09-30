import type { ComponentType } from 'react';
import type { ModuleId } from './ids';

export type GroupId = 'play' | 'songs' | 'recognize' | 'practice' | 'learn' | 'tools';

export const GROUPS: { id: GroupId; title: string }[] = [
  { id: 'play', title: 'Играть' },
  { id: 'songs', title: 'Песни' },
  { id: 'recognize', title: 'Распознать' },
  { id: 'practice', title: 'Практика' },
  { id: 'learn', title: 'Учить' },
  { id: 'tools', title: 'Инструменты' },
];

/**
 * Манифест модуля. Меню, панель команд (Ctrl+K), плитки и окна строятся по списку манифестов —
 * чтобы добавить раздел, достаточно создать папку модуля и добавить его в registry.ts.
 */
export interface ModuleDef {
  id: ModuleId;
  title: string;
  icon: string;
  group: GroupId;
  /** Одна строка для панели команд. */
  description: string;
  /** Дополнительные слова для поиска в панели команд. */
  keywords?: string[];
  View: ComponentType;
  /** Модуль новый в Studio — в меню помечается точкой. */
  isNew?: boolean;
}
