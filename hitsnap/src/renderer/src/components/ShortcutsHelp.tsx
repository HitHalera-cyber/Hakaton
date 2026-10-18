import { useEffect, useState } from 'react'
import { Modal } from './Modal'
import { Kbd } from './ui'

const KEYS: Array<[string, string]> = [
  ['Пробел', 'Повторить отрывок; после ответа — пауза или продолжить песню'],
  ['Esc', 'Следующая попытка (отрывок длиннее); в поиске — очистить строку'],
  ['Enter', 'Выбрать песню в поиске; после ответа — следующая песня'],
  ['↑ ↓', 'Перемещение по списку совпадений'],
  ['Ctrl + H', 'Подсказка'],
  ['1 – 4', 'Варианты в викторине; «кнопки» игроков на вечеринке'],
  ['← →', 'Выбор года в «Угадай год»'],
  ['F11', 'Полноэкранный режим'],
  ['?', 'Это окно']
]

/** Press "?" anywhere outside a text field to see every shortcut. */
export function ShortcutsHelp() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement
      if (e.key === '?' && !typing) {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return (
    <Modal open={open} onClose={() => setOpen(false)} title="Горячие клавиши">
      <div className="space-y-2.5">
        {KEYS.map(([k, what]) => (
          <div key={k} className="flex items-center gap-4 text-sm">
            <span className="w-24 shrink-0">
              <Kbd>{k}</Kbd>
            </span>
            <span className="text-muted">{what}</span>
          </div>
        ))}
      </div>
    </Modal>
  )
}
