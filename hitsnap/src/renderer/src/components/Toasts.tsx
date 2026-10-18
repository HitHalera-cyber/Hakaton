import { AnimatePresence, motion } from 'framer-motion'
import { useUi } from '@/store/ui'
import { cx } from './ui'

export function Toasts() {
  const toasts = useUi((s) => s.toasts)
  const dismiss = useUi((s) => s.dismiss)
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-80 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.button
            key={t.id}
            layout
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40 }}
            onClick={() => dismiss(t.id)}
            className={cx(
              'pointer-events-auto flex items-start gap-3 rounded-2xl border border-line bg-surface-2 p-4 text-left shadow-2xl backdrop-blur-xl cursor-pointer',
              t.tone === 'error' && 'border-bad/40'
            )}
          >
            {t.icon && <span className="text-2xl leading-none">{t.icon}</span>}
            <span>
              <span className="block text-sm font-semibold">{t.title}</span>
              {t.body && <span className="mt-0.5 block text-xs text-muted">{t.body}</span>}
            </span>
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  )
}
