import { dialog, BrowserWindow } from 'electron'
import { readdir, stat } from 'node:fs/promises'
import { extname, join, resolve, sep } from 'node:path'
import type { LocalTrack } from '@shared/types'
import { storage } from './storage'
import { parseTrackName } from './trackName'

// The player's own music: a folder they picked, scanned for audio files. Only
// files inside picked folders can be read — the renderer cannot ask for any
// other path.

const AUDIO = new Set(['.mp3', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.wav'])
const MAX_FILES = 5000
const MAX_DEPTH = 6
export const MAX_FILE_BYTES = 80 * 1024 * 1024
const KEY = 'allowed-music-folders'

function allowedFolders(): string[] {
  try {
    return JSON.parse(storage.get(KEY) ?? '[]') as string[]
  } catch {
    return []
  }
}

export function isAllowed(path: string): boolean {
  const full = resolve(path)
  return allowedFolders().some((f) => full === f || full.startsWith(f.endsWith(sep) ? f : f + sep))
}

export async function pickMusicFolder(win: BrowserWindow | null): Promise<string | null> {
  const options: Electron.OpenDialogOptions = { title: 'Папка с музыкой', properties: ['openDirectory'] }
  const res = win ? await dialog.showOpenDialog(win, options) : await dialog.showOpenDialog(options)
  if (res.canceled || !res.filePaths[0]) return null
  const folder = resolve(res.filePaths[0])
  const folders = allowedFolders()
  if (!folders.includes(folder)) await storage.set(KEY, JSON.stringify([...folders, folder]))
  return folder
}

export async function scanMusicFolder(folder: string): Promise<LocalTrack[]> {
  if (!isAllowed(folder)) throw new Error('Папка не выбрана в приложении')
  const tracks: LocalTrack[] = []
  const walk = async (dir: string, depth: number): Promise<void> => {
    if (depth > MAX_DEPTH || tracks.length >= MAX_FILES) return
    let entries: import('node:fs').Dirent[]
    try {
      entries = await readdir(dir, { withFileTypes: true })
    } catch {
      return
    }
    for (const e of entries) {
      if (tracks.length >= MAX_FILES) return
      if (e.name.startsWith('.')) continue
      const path = join(dir, e.name)
      if (e.isDirectory()) await walk(path, depth + 1)
      else if (AUDIO.has(extname(e.name).toLowerCase())) {
        try {
          if ((await stat(path)).size > MAX_FILE_BYTES) continue
        } catch {
          continue
        }
        tracks.push({ path, ...parseTrackName(path, dir) })
      }
    }
  }
  await walk(resolve(folder), 0)
  return tracks
}
