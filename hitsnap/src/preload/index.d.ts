import type { HitSnapApi } from '../shared/types'

declare global {
  interface Window {
    /** Present inside Electron; absent when the UI runs in a plain browser (`npm run dev:web`). */
    hitsnap?: HitSnapApi
  }
}

export {}
