import { createJSONStorage } from 'zustand/middleware'
import { api } from '@/lib/api'

/** zustand `persist` storage backed by the main process's JSON file. */
export const diskStorage = createJSONStorage(() => ({
  getItem: (key) => api.storageGet(key),
  setItem: (key, value) => api.storageSet(key, value),
  removeItem: (key) => api.storageRemove(key)
}))
