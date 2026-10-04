// Темы оформления. Цвета, шрифты, скругления и фактуры задаются в src/styles/themes.css
// через [data-theme="…"]; здесь — только список для выбора.

type BaseThemeId = 'vintage' | 'terminal' | 'slavic' | 'nav-swamp' | 'nav-winter' | 'nav-fire' | 'nav-koschei';
export type ThemeId = BaseThemeId | 'art-forest' | 'art-izba' | 'art-winter' | 'art-swamp' | 'art-forge' | 'art-volhv' | 'art-moon';

export interface ThemeInfo {
  id: ThemeId;
  name: string;
  description: string;
  /** Цвета для превью: фон, панель, акцент, гриф. */
  swatch: [string, string, string, string];
  /** Оформление с картиной: цвета берутся из темы base, картина — из src/styles/art.css. */
  base?: BaseThemeId;
  art?: string;
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
  // Оформления с картиной на фоне: окно программы поверх картины, панели полупрозрачные.
  {
    id: 'art-forest',
    name: 'Картина · Тёмный лес',
    description: 'Корявое дерево с вороном, кровавая луна и ельник в тумане',
    swatch: ['#0a090b', '#141216', '#b3121b', '#a03228'],
    base: 'slavic',
    art: 'forest',
  },
  {
    id: 'art-izba',
    name: 'Картина · Изба',
    description: 'Бревенчатая изба: резное окно, свечи, рушник и печь',
    swatch: ['#180e08', '#24160c', '#e08a2a', '#c8904a'],
    base: 'nav-fire',
    art: 'izba',
  },
  {
    id: 'art-winter',
    name: 'Картина · Зимний север',
    description: 'Волк на скале, ледяная снежинка и северное сияние',
    swatch: ['#080e1c', '#0e1628', '#8fd3ff', '#9cd0ff'],
    base: 'nav-winter',
    art: 'winter',
  },
  {
    id: 'art-swamp',
    name: 'Картина · Кикимора',
    description: 'Болото, Кикимора у корявого дерева, свечи и блуждающие огоньки',
    swatch: ['#06100c', '#0c1a12', '#4fe3a0', '#7fbf7a'],
    base: 'nav-swamp',
    art: 'swamp',
  },
  {
    id: 'art-forge',
    name: 'Картина · Сварог',
    description: 'Кузня Сварога: факел, огненное коло и искры над наковальней',
    swatch: ['#140804', '#1e0e08', '#ff8a1f', '#ff8a2a'],
    base: 'nav-fire',
    art: 'forge',
  },
  {
    id: 'art-volhv',
    name: 'Картина · Волхв',
    description: 'Волхв у идола, капище, крепость над рекой и Леший в облаках',
    swatch: ['#0c0c10', '#16161c', '#b3121b', '#c87a4a'],
    base: 'slavic',
    art: 'volhv',
  },
  {
    id: 'art-moon',
    name: 'Картина · Лунный лес',
    description: 'Дух девы среди берёз, ворон и полная луна',
    swatch: ['#080e1c', '#0e1628', '#6f9fe8', '#a8c8f0'],
    base: 'nav-winter',
    art: 'moon',
  },
];

export const DEFAULT_THEME: ThemeId = 'slavic';

/** Темы из старых версий (dark/light) и убранные темы («Болото», «Мара», «Купала», «Кощей») заменяются темой по умолчанию. */
export function migrateTheme(t: string | undefined): ThemeId {
  if (THEMES.some((x) => x.id === t)) return t as ThemeId;
  // Цвета убранных вариантов «Нави» остались только как основа для оформлений с картиной.
  return DEFAULT_THEME;
}

/** Поставить тему на страницу: цвета — data-theme, картина на фоне — data-art. */
export function applyTheme(id: ThemeId) {
  const t = THEMES.find((x) => x.id === id);
  const root = document.documentElement;
  root.dataset.theme = t?.base ?? id;
  if (t?.art) root.dataset.art = t.art;
  else delete root.dataset.art;
}
