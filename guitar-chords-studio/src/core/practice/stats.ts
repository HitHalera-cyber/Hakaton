// Статистика занятий: серия дней подряд, последние дни, итоги.

export interface DayStat {
  seconds: number;
  chords: string[];
}

const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Сколько дней подряд (до сегодня или до вчера включительно) вы занимались хотя бы minSeconds. */
export function streak(days: Record<string, DayStat>, today = new Date(), minSeconds = 60): number {
  const d = new Date(today);
  const active = (x: Date) => (days[key(x)]?.seconds ?? 0) >= minSeconds;
  if (!active(d)) d.setDate(d.getDate() - 1); // сегодня ещё можно успеть
  let n = 0;
  while (active(d)) {
    n++;
    d.setDate(d.getDate() - 1);
  }
  return n;
}

/** Последние n дней (от старых к новым) с минутами занятий. */
export function lastDays(days: Record<string, DayStat>, n = 14, today = new Date()): { key: string; label: string; minutes: number }[] {
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const k = key(d);
    out.push({
      key: k,
      label: `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`,
      minutes: Math.round((days[k]?.seconds ?? 0) / 60),
    });
  }
  return out;
}

export function totalMinutes(days: Record<string, DayStat>): number {
  return Math.round(Object.values(days).reduce((a, d) => a + d.seconds, 0) / 60);
}
