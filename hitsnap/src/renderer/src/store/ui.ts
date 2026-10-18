import { create } from 'zustand'

export type Screen = 'home' | 'game' | 'collections' | 'arcade' | 'library' | 'stats' | 'settings'

export interface Toast {
  id: number
  title: string
  body?: string
  icon?: string
  tone?: 'info' | 'success' | 'error'
}

interface UiStore {
  screen: Screen
  toasts: Toast[]
  go: (screen: Screen) => void
  toast: (t: Omit<Toast, 'id'>) => void
  dismiss: (id: number) => void
}

let nextId = 1

export const useUi = create<UiStore>()((set, get) => ({
  screen: 'home',
  toasts: [],
  go: (screen) => set({ screen }),
  toast: (t) => {
    const id = nextId++
    set({ toasts: [...get().toasts, { ...t, id }] })
    setTimeout(() => get().dismiss(id), 4500)
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) })
}))
