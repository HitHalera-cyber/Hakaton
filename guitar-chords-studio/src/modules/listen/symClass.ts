/** Класс размера для крупного названия аккорда: длинные названия — мельче. */
export const symClass = (s: string) => (s.length > 7 ? 'xlong' : s.length > 4 ? 'long' : '');
