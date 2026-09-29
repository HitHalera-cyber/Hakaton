// Темы оформления. Цвета, шрифты, скругления и фактуры задаются в src/styles/themes.css
// через [data-theme="…"]; здесь — только список для выбора.

export type ThemeId =
  | 'studio'
  | 'minimal'
  | 'vintage'
  | 'synthwave'
  | 'pixel'
  | 'terminal'
  | 'glass'
  | 'brutal'
  | 'rock'
  | 'notebook'
  | 'slavic'
  | 'nav-swamp'
  | 'nav-winter'
  | 'nav-fire'
  | 'nav-koschei';

export interface ThemeInfo {
  id: ThemeId;
  name: string;
  description: string;
  /** Цвета для превью: фон, панель, акцент, гриф. */
  swatch: [string, string, string, string];
}

export const THEMES: ThemeInfo[] = [
  {
    id: 'studio',
    name: 'Студия',
    description: 'Тёмный графит и оранжевый акцент — спокойно и профессионально',
    swatch: ['#13151b', '#1f232d', '#f5a524', '#4a2f1c'],
  },
  {
    id: 'minimal',
    name: 'Минимализм',
    description: 'Белый, воздух и тонкие линии, ничего лишнего',
    swatch: ['#f7f7f5', '#ffffff', '#111111', '#c9a27c'],
  },
  {
    id: 'vintage',
    name: 'Винтаж',
    description: 'Ламповый усилитель: кремовый, коричневая кожа и золото',
    swatch: ['#2b1d14', '#f3e6cc', '#b8862b', '#5b3420'],
  },
  {
    id: 'synthwave',
    name: 'Синтвейв',
    description: 'Неон 80-х: фиолетовая ночь, розовый и бирюзовый свет',
    swatch: ['#12051f', '#1d0b33', '#ff2fb3', '#2a0f47'],
  },
  {
    id: 'pixel',
    name: '8 бит',
    description: 'Ретро-игра: пиксельный шрифт, толстые рамки, яркая палитра',
    swatch: ['#1b1b3a', '#2c2c5a', '#ffd23f', '#6b3e26'],
  },
  {
    id: 'terminal',
    name: 'Терминал',
    description: 'Зелёный люминофор на чёрном, моноширинный шрифт',
    swatch: ['#050805', '#0b120b', '#33ff66', '#0f1f0f'],
  },
  {
    id: 'glass',
    name: 'Стекло',
    description: 'Морской градиент и полупрозрачные «матовые» панели',
    swatch: ['#0f4c75', '#ffffff55', '#00e0c6', '#3a2a4a'],
  },
  {
    id: 'brutal',
    name: 'Брутализм',
    description: 'Жёлтый и чёрный, толстые рамки и жёсткие тени',
    swatch: ['#ffe600', '#ffffff', '#000000', '#1a1a1a'],
  },
  {
    id: 'rock',
    name: 'Рок',
    description: 'Чёрный металл, красный огонь и узкий плакатный шрифт',
    swatch: ['#0a0a0a', '#161616', '#e10600', '#1c1c1c'],
  },
  {
    id: 'notebook',
    name: 'Тетрадь',
    description: 'Клетчатая бумага, синие чернила и рукописные заголовки',
    swatch: ['#fbfaf4', '#ffffff', '#1e40af', '#d9b98c'],
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

export const DEFAULT_THEME: ThemeId = 'studio';

/** Темы из старых версий: dark/light. */
export function migrateTheme(t: string | undefined): ThemeId {
  if (t === 'light') return 'minimal';
  if (THEMES.some((x) => x.id === t)) return t as ThemeId;
  return DEFAULT_THEME;
}
