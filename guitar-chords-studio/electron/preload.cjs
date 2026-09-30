// Мост между интерфейсом и главным процессом: только информация о версии и обновления.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gc', {
  info: () => ipcRenderer.invoke('app:info'),
  checkUpdates: () => ipcRenderer.invoke('update:check'),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.invoke('update:install'),
  openReleases: () => ipcRenderer.invoke('app:open-releases'),
  printToPdf: (name) => ipcRenderer.invoke('print:pdf', name),
  onUpdate: (cb) => {
    const listener = (_e, status) => cb(status);
    ipcRenderer.on('update:status', listener);
    return () => ipcRenderer.removeListener('update:status', listener);
  },
});
