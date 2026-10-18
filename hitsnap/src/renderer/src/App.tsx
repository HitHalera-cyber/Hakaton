import { AnimatePresence, motion } from 'framer-motion'
import { useEffect } from 'react'
import { Sidebar } from './components/Sidebar'
import { Toasts } from './components/Toasts'
import { useTheme } from './hooks/useTheme'
import { audio } from './lib/audio'
import { isDemo } from './lib/api'
import { GameScreen } from './screens/GameScreen'
import { CollectionsScreen } from './screens/CollectionsScreen'
import { HomeScreen } from './screens/HomeScreen'
import { LibraryScreen } from './screens/LibraryScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { StatsScreen } from './screens/StatsScreen'
import { useSettings } from './store/settings'
import { useUi, type Screen } from './store/ui'

const SCREENS: Record<Screen, () => React.JSX.Element> = {
  home: HomeScreen,
  game: GameScreen,
  collections: CollectionsScreen,
  library: LibraryScreen,
  stats: StatsScreen,
  settings: SettingsScreen
}

export function App() {
  useTheme()
  const screen = useUi((s) => s.screen)
  const volume = useSettings((s) => s.volume)
  useEffect(() => audio.setVolume(volume), [volume])

  const Current = SCREENS[screen]
  return (
    <div className="relative flex h-full">
      <div className="ambient" />
      <Sidebar />
      <main className="relative z-10 flex min-w-0 flex-1 flex-col">
        <div className="drag h-11 shrink-0" />
        {isDemo && (
          <div className="mx-8 mb-2 rounded-xl border border-warn/30 bg-warn/10 px-4 py-2 text-xs text-warn">
            Демо-режим в браузере: вместо настоящих песен звучат синтезированные мелодии. Запустите приложение через Electron, чтобы играть с реальными превью.
          </div>
        )}
        <AnimatePresence mode="wait">
          <motion.div
            key={screen}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="min-h-0 flex-1 overflow-y-auto px-8 pb-8"
          >
            <Current />
          </motion.div>
        </AnimatePresence>
      </main>
      <Toasts />
    </div>
  )
}
