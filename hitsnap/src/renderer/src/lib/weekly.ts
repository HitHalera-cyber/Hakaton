import type { Filters } from './game'
import { hashString } from './random'

// «Испытание недели»: ten songs on a theme that changes every Monday — the
// same songs for everyone, so results can be compared with friends.

export const WEEKLY_ROUNDS = 10

export interface WeeklyTheme {
  title: string
  emoji: string
  from: string
  to: string
  filters: Partial<Filters>
}

export const WEEKLY_THEMES: WeeklyTheme[] = [
  { title: 'Хиты 80-х', emoji: '📼', from: '#db2777', to: '#4f46e5', filters: { decades: [1980] } },
  { title: 'Русский рок', emoji: '🎸', from: '#b91c1c', to: '#1f2937', filters: { genres: ['russian-rock'] } },
  { title: 'Нулевые', emoji: '📱', from: '#2563eb', to: '#0f766e', filters: { decades: [2000] } },
  { title: 'Электроника', emoji: '🎛️', from: '#06b6d4', to: '#7c3aed', filters: { genres: ['electronic'] } },
  { title: 'Кино и игры', emoji: '🎬', from: '#f59e0b', to: '#7c2d12', filters: { genres: ['soundtrack'] } },
  { title: 'Хип-хоп', emoji: '🎤', from: '#facc15', to: '#ea580c', filters: { genres: ['hiphop'] } },
  { title: 'Девяностые', emoji: '💿', from: '#0891b2', to: '#7c3aed', filters: { decades: [1990] } },
  { title: 'Русская эстрада', emoji: '🎙️', from: '#e11d48', to: '#9333ea', filters: { genres: ['russian-pop'] } },
  { title: 'Рок-классика', emoji: '🤘', from: '#475569', to: '#b91c1c', filters: { genres: ['rock'], decades: [1960, 1970, 1980] } },
  { title: 'Диско и фанк', emoji: '🪩', from: '#ec4899', to: '#f59e0b', filters: { genres: ['disco'] } },
  { title: 'Хиты 2010-х', emoji: '🎧', from: '#9333ea', to: '#e11d48', filters: { decades: [2010] } },
  { title: 'Советская эстрада', emoji: '☭', from: '#dc2626', to: '#ca8a04', filters: { genres: ['soviet'] } },
  { title: 'Метал', emoji: '⚡', from: '#18181b', to: '#71717a', filters: { genres: ['metal'] } },
  { title: 'Свежее: 2020-е', emoji: '🚀', from: '#16a34a', to: '#0284c7', filters: { decades: [2020] } },
  { title: 'Русский рэп', emoji: '🧢', from: '#0f172a', to: '#be123c', filters: { genres: ['russian-rap'] } },
  { title: 'Латино', emoji: '💃', from: '#f97316', to: '#dc2626', filters: { genres: ['latin'] } }
]

/** Monday of the date's week as YYYY-MM-DD — the key of that week's challenge. */
export function weekKey(date = new Date()): string {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function weeklyChallenge(key = weekKey()): { key: string; theme: WeeklyTheme; seed: number } {
  const seed = hashString(`hitsnap-week-${key}`)
  return { key, theme: WEEKLY_THEMES[seed % WEEKLY_THEMES.length], seed }
}

/** Days until the next theme. */
export function daysLeftInWeek(date = new Date()): number {
  return 7 - ((date.getDay() + 6) % 7)
}
