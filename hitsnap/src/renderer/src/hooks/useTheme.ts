import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useSettings } from '@/store/settings'

/** Applies the theme + accent to <html> and keeps the window title bar in sync. */
export function useTheme(): boolean {
  const theme = useSettings((s) => s.theme)
  const accent = useSettings((s) => s.accent)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const dark = theme === 'dark' || (theme === 'system' && systemDark)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', dark)
    root.dataset.accent = accent
    api.setTitleBarTheme(dark)
  }, [dark, accent])

  return dark
}
