// Разделы программы, сгруппированные для бокового меню.

export type TabId =
  | 'sound'
  | 'sequence'
  | 'metronome'
  | 'listen'
  | 'song'
  | 'circle'
  | 'library'
  | 'scales'
  | 'key'
  | 'trainer'
  | 'tuner'
  | 'midi'
  | 'favorites';

export interface NavItem {
  id: TabId;
  icon: string;
  label: string;
}

export const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Играть',
    items: [
      { id: 'sound', icon: '🔊', label: 'Звук' },
      { id: 'sequence', icon: '🎵', label: 'Последовательность' },
      { id: 'metronome', icon: '⏱', label: 'Метроном' },
    ],
  },
  {
    title: 'Распознать',
    items: [
      { id: 'listen', icon: '👂', label: 'Слушать гитару' },
      { id: 'song', icon: '🎧', label: 'Разбор песни' },
      { id: 'circle', icon: '⭕', label: 'Квинтовый круг' },
    ],
  },
  {
    title: 'Учить',
    items: [
      { id: 'library', icon: '📖', label: 'Справочник' },
      { id: 'scales', icon: '🎼', label: 'Гаммы' },
      { id: 'key', icon: '🗝', label: 'Тональность' },
      { id: 'trainer', icon: '🎯', label: 'Тренажёр' },
    ],
  },
  {
    title: 'Инструменты',
    items: [
      { id: 'tuner', icon: '🎤', label: 'Тюнер' },
      { id: 'midi', icon: '🎹', label: 'MIDI' },
      { id: 'favorites', icon: '⭐', label: 'Избранное и история' },
    ],
  },
];

export const ALL_TABS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);
export const isTab = (t: string): t is TabId => ALL_TABS.some((x) => x.id === t);
