import type { LayoutId } from '../../store/model';

export const LAYOUTS: { id: LayoutId; name: string; description: string }[] = [
  { id: 'classic', name: 'Классика', description: 'Меню слева, гриф сверху, под ним аккорд и выбранный раздел' },
  { id: 'dashboard', name: 'Приборная панель', description: 'Гриф, аккорд и четыре плитки с разделами видны сразу' },
  { id: 'listener', name: 'Слушатель', description: 'Для живой игры: крупно услышанный аккорд, круг и история' },
];
