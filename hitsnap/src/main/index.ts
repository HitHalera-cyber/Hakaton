import { app, BrowserWindow, ipcMain, nativeTheme, screen, shell } from 'electron'
import { join } from 'node:path'
import type { Song } from '@shared/types'
import { cacheInfo, clearCache, resolveTrack } from './services/audioCache'
import { searchCatalog } from './services/providers'
import { storage } from './services/storage'

const isMac = process.platform === 'darwin'

const overlay = (dark: boolean): Electron.TitleBarOverlay => ({
  color: '#00000000',
  symbolColor: dark ? '#e7e5f4' : '#28243d',
  height: 44
})

function createWindow(): BrowserWindow {
  const { workAreaSize } = screen.getPrimaryDisplay()
  const win = new BrowserWindow({
    width: Math.min(1280, Math.round(workAreaSize.width * 0.85)),
    height: Math.min(840, Math.round(workAreaSize.height * 0.9)),
    minWidth: 900,
    minHeight: 620,
    show: false,
    title: 'HitSnap',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#0c0a17' : '#f6f5fb',
    titleBarStyle: 'hidden',
    ...(isMac ? { trafficLightPosition: { x: 16, y: 14 } } : { titleBarOverlay: overlay(nativeTheme.shouldUseDarkColors) }),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true
    }
  })

  win.once('ready-to-show', () => win.show())

  // Every link opens in the user's browser, never inside the app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https:\/\//.test(url)) void shell.openExternal(url)
    return { action: 'deny' }
  })

  if (process.env['ELECTRON_RENDERER_URL']) void win.loadURL(process.env['ELECTRON_RENDERER_URL'])
  else void win.loadFile(join(__dirname, '../renderer/index.html'))
  return win
}

function registerIpc(): void {
  ipcMain.handle('track:resolve', (_e, song: Song) => resolveTrack(song))
  ipcMain.handle('catalog:search', (_e, query: string) => searchCatalog(query))
  ipcMain.handle('cache:info', () => cacheInfo())
  ipcMain.handle('cache:clear', () => clearCache())
  ipcMain.handle('storage:get', (_e, key: string) => storage.get(key))
  ipcMain.handle('storage:set', (_e, key: string, value: string) => storage.set(key, value))
  ipcMain.handle('storage:remove', (_e, key: string) => storage.remove(key))
  ipcMain.handle('shell:open', (_e, url: string) => {
    if (/^https:\/\//.test(url)) return shell.openExternal(url)
  })
  ipcMain.on('titlebar:theme', (e, dark: boolean) => {
    const win = BrowserWindow.fromWebContents(e.sender)
    if (win && !isMac) win.setTitleBarOverlay(overlay(dark))
  })
}

app.whenReady().then(() => {
  registerIpc()
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (!isMac) app.quit()
})
