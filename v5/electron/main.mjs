// Electron main process - plain JavaScript ES module
// Run with: electron electron/main.mjs

import { app, BrowserWindow, ipcMain, shell, Tray, Menu, nativeImage, powerMonitor } from 'electron';
import { spawn } from 'child_process';
import { join } from 'path';
import { existsSync, readFileSync, writeFileSync } from 'fs';

let win = null;
let tray = null;
let backendProcess = null;
let isQuitting = false;

const BACKEND_PORT = 8000;
const workspaceRoot = join(__dirname, '..', '..');

function backendDir() {
  return app.isPackaged
    ? join(process.resourcesPath, 'backend')
    : join(workspaceRoot, 'ARIA_APP', 'backend');
}

function pythonExecutable() {
  if (app.isPackaged) {
    const bundled = join(process.resourcesPath, 'python', 'python.exe');
    if (existsSync(bundled)) return bundled;
    console.warn('[Backend] runtime embebido ausente → usando Python del sistema');
    return process.platform === 'win32' ? 'python' : 'python3';
  }
  const venv = join(workspaceRoot, '.venv', 'Scripts', 'python.exe');
  if (existsSync(venv)) return venv;
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startBackend() {
  const dir = backendDir();
  if (!existsSync(join(dir, 'app.py'))) {
    console.warn('[Backend] app.py no encontrado en', dir, '→ modo offline');
    return;
  }

  const executable = pythonExecutable();
  const args = ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];
  console.log('[Backend] Iniciando:', executable, args.join(' '));

  backendProcess = spawn(executable, args, {
    cwd: dir,
    env: { ...process.env, BACKEND_PORT: String(BACKEND_PORT), PYTHONUNBUFFERED: '1' },
    stdio: 'pipe',
  });

  backendProcess.stdout?.on('data', (chunk) => process.stdout.write(`[Backend] ${chunk.toString()}`));
  backendProcess.stderr?.on('data', (chunk) => process.stderr.write(`[Backend] ${chunk.toString()}`));
  backendProcess.on('error', (error) => console.error('[Backend] spawn error:', error));
}

function stopBackend() {
  if (!backendProcess) return;
  try {
    backendProcess.kill();
  } catch (error) {
    console.error('[Backend] kill error:', error);
  }
  backendProcess = null;
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 620,
    show: false,
    title: 'ARIA OS v5.0',
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0e27',
    vibrancy: 'under-window',
    visualEffectState: 'active',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      backgroundThrottling: false,
    },
    icon: join(__dirname, '..', 'assets', 'icon.png'),
  });

  win.once('ready-to-show', () => win?.show());

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    win.loadURL(devServerUrl);
    win.webContents.openDevTools({ mode: 'detach' });
  } else {
    win.loadFile(join(__dirname, '..', 'dist', 'index.html'));
  }

  win.webContents.on('console-message', (_event, level, message) => {
    console.log(`[Renderer:${level}] ${message}`);
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  win.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      win?.hide();
    }
  });

  win.on('closed', () => {
    win = null;
  });
}

function createTray() {
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAFklEQVR42mNk+M9QzwAFGC8A2QCqgH9zAAAAAElFTkSuQmCC'
  );
  const menu = Menu.buildFromTemplate([
    { label: 'Mostrar ARIA', click: () => win?.show() },
    { type: 'separator' },
    {
      label: 'Salir',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
  tray = new Tray(icon);
  tray.setToolTip('ARIA OS v5.0');
  tray.setContextMenu(menu);
  tray.on('click', () => win?.show());
}

function settingsFile() {
  return join(app.getPath('userData'), 'settings.json');
}

function readSettings() {
  try {
    const file = settingsFile();
    if (!existsSync(file)) return {};
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    console.error('[Settings] read error:', error);
    return {};
  }
}

function writeSettings(settings) {
  try {
    writeFileSync(settingsFile(), JSON.stringify(settings, null, 2), 'utf8');
    return { ok: true };
  } catch (error) {
    console.error('[Settings] write error:', error);
    return { ok: false };
  }
}

ipcMain.handle('chat:send', async (_event, message) => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return await response.json();
  } catch (error) {
    return { error: String(error) };
  }
});

ipcMain.handle('skills:load', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/skills`);
    return await response.json();
  } catch {
    return [];
  }
});

ipcMain.handle('system:status', async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/system/status`);
    return await response.json();
  } catch {
    return { status: 'offline' };
  }
});

ipcMain.handle('settings:get', async () => readSettings());
ipcMain.handle('settings:set', async (_event, settings) => writeSettings(settings));

ipcMain.handle('window:minimize', () => win?.minimize());
ipcMain.handle('window:maximize', () => {
  if (win?.isMaximized()) win.unmaximize();
  else win?.maximize();
});
ipcMain.handle('window:close', () => win?.close());
ipcMain.handle('window:show', () => win?.show());
ipcMain.handle('window:opacity', (_event, value) => {
  const clamped = Math.min(100, Math.max(20, Number(value) || 100));
  win?.setOpacity(clamped / 100);
});

app.whenReady().then(() => {
  startBackend();
  createWindow();
  createTray();

  powerMonitor.on('suspend', () => console.log('[System] Suspended'));
  powerMonitor.on('resume', () => console.log('[System] Resumed'));

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (isQuitting) {
    stopBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  stopBackend();
});