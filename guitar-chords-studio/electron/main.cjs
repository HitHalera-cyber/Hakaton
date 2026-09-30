// Главный процесс Electron (GuitarChords Studio): окно, протокол app:// для файлов интерфейса и сэмплов,
// разрешения (MIDI, микрофон), сохранение песен в PDF. Автообновления у Studio нет — это отдельная сборка.
const { app, BrowserWindow, Menu, session, shell, protocol, net, ipcMain, dialog } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

const ALLOWED_PERMISSIONS = new Set(['midi', 'midiSysex', 'media', 'audioCapture', 'clipboard-sanitized-write']);
const DIST = path.join(__dirname, '..', 'dist');
const RELEASES_URL = 'https://github.com/HitHalera-cyber/Hakaton/releases';
const isPortable = Boolean(process.env.PORTABLE_EXECUTABLE_DIR);

// Свой протокол вместо file:// — чтобы fetch() мог загружать сэмплы и работали безопасные API.
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

let win = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1080,
    minHeight: 680,
    title: 'Гитарные аккорды — Studio',
    backgroundColor: '#0b0c0e',
    icon: path.join(__dirname, '..', 'build', 'icon.png'),
    autoHideMenuBar: true,
    // Показываем окно, когда страница уже отрисована, — без вспышки пустого или «чужого» интерфейса.
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  win.once('ready-to-show', () => win.show());

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  win.loadURL(devUrl || 'app://bundle/index.html');

  // F12 — инструменты разработчика, Ctrl+R — перезагрузка (меню скрыто).
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return;
    if (input.key === 'F12') {
      win.webContents.toggleDevTools();
      event.preventDefault();
    } else if (input.control && input.key.toLowerCase() === 'r') {
      win.webContents.reload();
      event.preventDefault();
    }
  });

  // Никогда не уходить со страницы программы (например, если бросить файл в окно).
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('app://') && !(devUrl && url.startsWith(devUrl))) event.preventDefault();
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ---------- Автообновление ----------
function sendUpdate(status) {
  if (win && !win.isDestroyed()) win.webContents.send('update:status', status);
}

let updater = null;
function setupUpdater() {
  // Studio не публикует релизы — обновляется новой сборкой вручную.
  if (!process.env.GC_ENABLE_UPDATES) return;
  // Portable-версия и неподписанная macOS-сборка обновляются вручную; в Linux — только AppImage.
  if (!app.isPackaged || isPortable || process.platform === 'darwin') return;
  if (process.platform === 'linux' && !process.env.APPIMAGE) return;
  try {
    ({ autoUpdater: updater } = require('electron-updater'));
  } catch {
    return;
  }
  updater.autoDownload = false;
  updater.autoInstallOnAppQuit = true;
  updater.on('checking-for-update', () => sendUpdate({ state: 'checking' }));
  updater.on('update-available', (info) => sendUpdate({ state: 'available', version: info.version }));
  updater.on('update-not-available', () => sendUpdate({ state: 'none' }));
  updater.on('download-progress', (p) => sendUpdate({ state: 'downloading', percent: Math.round(p.percent) }));
  updater.on('update-downloaded', (info) => sendUpdate({ state: 'downloaded', version: info.version }));
  updater.on('error', (e) => sendUpdate({ state: 'error', message: String(e && e.message ? e.message : e).slice(0, 200) }));
  // Проверяем через несколько секунд после запуска, чтобы не мешать старту.
  setTimeout(() => updater.checkForUpdates().catch(() => {}), 4000);
}

ipcMain.handle('app:info', () => ({
  version: app.getVersion(),
  portable: isPortable,
  updatesSupported: Boolean(updater),
  releasesUrl: RELEASES_URL,
}));
ipcMain.handle('update:check', async () => {
  if (!updater) return sendUpdate({ state: 'unsupported' });
  await updater.checkForUpdates().catch((e) => sendUpdate({ state: 'error', message: String(e.message || e) }));
});
ipcMain.handle('update:download', async () => {
  if (updater) await updater.downloadUpdate().catch((e) => sendUpdate({ state: 'error', message: String(e.message || e) }));
});
ipcMain.handle('update:install', () => {
  if (updater) updater.quitAndInstall(false, true);
});
ipcMain.handle('app:open-releases', () => shell.openExternal(RELEASES_URL));

// Сохранить страницу (печатную версию песни) в PDF.
ipcMain.handle('print:pdf', async (event, name) => {
  const owner = BrowserWindow.fromWebContents(event.sender);
  const { canceled, filePath } = await dialog.showSaveDialog(owner, {
    defaultPath: `${String(name || 'Песня').replace(/[\\/:*?"<>|]/g, '_')}.pdf`,
    filters: [{ name: 'PDF', extensions: ['pdf'] }],
  });
  if (canceled || !filePath) return false;
  const data = await event.sender.printToPDF({ printBackground: true, pageSize: 'A4' });
  fs.writeFileSync(filePath, data);
  shell.showItemInFolder(filePath);
  return true;
});

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);

  protocol.handle('app', (request) => {
    const { pathname } = new URL(request.url);
    const file = path.normalize(path.join(DIST, decodeURIComponent(pathname)));
    if (!file.startsWith(DIST)) return new Response('Forbidden', { status: 403 });
    return net.fetch(pathToFileURL(file).toString());
  });

  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(ALLOWED_PERMISSIONS.has(permission));
  });
  session.defaultSession.setPermissionCheckHandler((_wc, permission) => ALLOWED_PERMISSIONS.has(permission));

  createWindow();
  setupUpdater();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
