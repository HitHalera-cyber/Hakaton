// Темы оформления. Цвета, шрифты, скругления и фактуры задаются в src/styles/themes.css
// через [data-theme="…"]; здесь — только список для выбора.

export type ThemeId = 'vintage' | 'terminal' | 'slavic' | 'nav-swamp' | 'nav-winter' | 'nav-fire' | 'nav-koschei';

export interface ThemeInfo {
  id: ThemeId;
  name: string;
  description: string;
  /** Цвета для превью: фон, панель, акцент, гриф. */
  swatch: [string, string, string, string];
}

export const THEMES: ThemeInfo[] = [
  {
    id: 'vintage',
    name: 'Винтаж',
    description: 'Ламповый усилитель: кремовый, коричневая кожа и золото',
    swatch: ['#2b1d14', '#f3e6cc', '#b8862b', '#5b3420'],
  },
  {
    id: 'terminal',
    name: 'Терминал',
    description: 'Зелёный люминофор на чёрном, моноширинный шрифт',
    swatch: ['#050805', '#0b120b', '#33ff66', '#0f1f0f'],
  },
  {
    id: 'slavic',
    name: 'Навь',
    description: 'Славянское тёмное фэнтези: ночной ельник, бронза, угли и кровь',
    swatch: ['#0b0c0e', '#141517', '#b3121b', '#8a6a3a'],
  },
  {
    id: 'nav-swamp',
    name: 'Навь · Болото',
    description: 'Трясина, камыш и блуждающие огоньки: патина, мох и призрачный зелёный свет',
    swatch: ['#060d0a', '#0f1712', '#4fe3a0', '#4f7a63'],
  },
  {
    id: 'nav-winter',
    name: 'Навь · Мара',
    description: 'Владения Мораны: ледяная ночь, серебро, заснеженный ельник и холодное сияние',
    swatch: ['#070b14', '#0e1522', '#8fd3ff', '#a8b6c8'],
  },
  {
    id: 'nav-fire',
    name: 'Навь · Купала',
    description: 'Купальская ночь: зарево костра за чёрным лесом, золото и искры',
    swatch: ['#0c0705', '#150e0a', '#ff8a1f', '#c98a2a'],
  },
  {
    id: 'nav-koschei',
    name: 'Навь · Кощей',
    description: 'Кощеево царство: чёрно-фиолетовая тьма, голые деревья, старое золото и аметисты',
    swatch: ['#09070d', '#120f18', '#d8b44a', '#9b4fe0'],
  },
];

export const DEFAULT_THEME: ThemeId = 'slavic';

/** Темы из старых версий (dark/light) и убранные темы заменяются темой по умолчанию. */
export function migrateTheme(t: string | undefined): ThemeId {
  if (THEMES.some((x) => x.id === t)) return t as ThemeId;
  return DEFAULT_THEME;
}
