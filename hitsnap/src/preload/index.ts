import { contextBridge, ipcRenderer } from 'electron'
import type { HitSnapApi } from '@shared/types'

const api: HitSnapApi = {
  platform: process.platform,
  resolveTrack: (song) => ipcRenderer.invoke('track:resolve', song),
  searchCatalog: (query) => ipcRenderer.invoke('catalog:search', query),
  fetchPlaylist: (link) => ipcRenderer.invoke('catalog:playlist', link),
  fetchChart: () => ipcRenderer.invoke('catalog:chart'),
  pickMusicFolder: () => ipcRenderer.invoke('local:pick'),
  scanMusicFolder: (folder) => ipcRenderer.invoke('local:scan', folder),
  cacheInfo: () => ipcRenderer.invoke('cache:info'),
  clearCache: () => ipcRenderer.invoke('cache:clear'),
  storageGet: (key) => ipcRenderer.invoke('storage:get', key),
  storageSet: (key, value) => ipcRenderer.invoke('storage:set', key, value),
  storageRemove: (key) => ipcRenderer.invoke('storage:remove', key),
  openExternal: (url) => ipcRenderer.invoke('shell:open', url),
  setTitleBarTheme: (dark) => ipcRenderer.send('titlebar:theme', dark)
}

contextBridge.exposeInMainWorld('hitsnap', api)
