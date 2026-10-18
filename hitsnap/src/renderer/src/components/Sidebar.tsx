import { BarChart3, Dices, Gamepad2, LayoutGrid, Library, Moon, Radio, Settings, Sun, SunMoon } from 'lucide-react'
import type { ComponentType } from 'react'
import { useGame } from '@/store/game'
import { useSettings, type ThemePref } from '@/store/settings'
import { useUi, type Screen } from '@/store/ui'
import { LevelBadge } from './LevelBadge'
import { Logo } from './Logo'
import { cx } from './ui'

const NAV: Array<{ screen: Screen; label: string; icon: ComponentType<{ size?: number }> }> = [
  { screen: 'home', label: 'Играть', icon: Gamepad2 },
  { screen: 'collections', label: 'Подборки', icon: LayoutGrid },
  { screen: 'arcade', label: 'Игротека', icon: Dices },
  { screen: 'radio', label: 'Радио', icon: Radio },
  { screen: 'library', label: 'Библиотека', icon: Library },
  { screen: 'stats', label: 'Статистика', icon: BarChart3 },
  { screen: 'settings', label: 'Настройки', icon: Settings }
]

const THEME_NEXT: Record<ThemePref, ThemePref> = { system: 'light', light: 'dark', dark: 'system' }
const THEME_LABEL: Record<ThemePref, string> = { system: 'Как в системе', light: 'Светлая', dark: 'Тёмная' }

export function Sidebar() {
  const screen = useUi((s) => s.screen)
  const go = useUi((s) => s.go)
  const phase = useGame((s) => s.phase)
  const theme = useSettings((s) => s.theme)
  const update = useSettings((s) => s.update)
  const profileName = useSettings((s) => s.profileName)
  const profileEmoji = useSettings((s) => s.profileEmoji)
  const inGame = phase !== 'idle'
  const live = phase === 'loading' || phase === 'playing' || phase === 'reveal'
  const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : SunMoon

  return (
    <aside className="relative z-10 flex w-60 shrink-0 flex-col border-r border-line px-3 pb-4 pt-14">
      <div className="drag absolute inset-x-0 top-0 h-12" />
      <div className="mb-8 px-3">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ screen: s, label, icon: Icon }) => {
          const target: Screen = s === 'home' && inGame ? 'game' : s
          const active = screen === s || (s === 'home' && screen === 'game')
          return (
            <button
              key={s}
              onClick={() => go(target)}
              className={cx(
                'group relative flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition cursor-pointer',
                active ? 'bg-accent/12 text-fg' : 'text-muted hover:bg-fg/5 hover:text-fg'
              )}
            >
              {active && <span className="bg-gradient-accent absolute left-0 top-2.5 h-6 w-1 rounded-full" />}
              <span className={cx(active && 'text-accent')}>
                <Icon size={18} />
              </span>
              {label}
              {s === 'home' && live && <span className="ml-auto h-2 w-2 animate-pulse rounded-full bg-accent" title="Идёт игра" />}
            </button>
          )
        })}
      </nav>
      <div className="mt-auto">
        <button
          onClick={() => go('settings')}
          className="mb-1 flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-fg/5 cursor-pointer"
          title="Профиль"
        >
          <span className="bg-gradient-accent flex h-8 w-8 items-center justify-center rounded-lg text-lg">{profileEmoji}</span>
          <span className={cx('truncate font-semibold', !profileName && 'font-normal text-muted')}>{profileName || 'Задать имя'}</span>
        </button>
        <button
          onClick={() => go('stats')}
          className="mb-2 w-full rounded-xl px-3 py-2 text-left transition hover:bg-fg/5 cursor-pointer"
          title="Уровень и статистика"
        >
          <LevelBadge />
        </button>
        <button
          onClick={() => update({ theme: THEME_NEXT[theme] })}
          className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium text-muted transition hover:bg-fg/5 hover:text-fg cursor-pointer"
          title="Сменить тему"
        >
          <ThemeIcon size={18} />
          Тема: {THEME_LABEL[theme]}
        </button>
      </div>
    </aside>
  )
}
