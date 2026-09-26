const { app, BrowserWindow, Tray, Menu, ipcMain, globalShortcut, screen, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';
const FRONTEND_URL = process.env.AURA_FRONTEND_URL || `http://localhost:8000/dashboard`;

let mainWindow = null;
let tray = null;
let backendProcess = null;
let isQuitting = false;
let shortcutsRegistered = false;

const SHORTCUTS = {
  show: 'Ctrl+Alt+A',
  hide: 'Ctrl+Alt+H',
  toggle: 'Ctrl+Alt+T',
};

function getPythonExe() {
  const venv = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venv)) return venv;
  return process.execPath.replace('\\electron.exe', '\\python.exe');
}

function startBackend() {
  if (backendProcess) return;
  const pythonExe = getPythonExe();
  backendProcess = spawn(pythonExe, ['-m', 'uvicorn', 'backend.main:app', '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONDONTWRITEBYTECODE: '1' },
    stdio: 'ignore',
  });
  backendProcess.on('exit', (code) => {
    console.log('[Backend] exited with code', code);
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) return;
  backendProcess.kill('SIGTERM');
  setTimeout(() => { if (backendProcess) backendProcess.kill('SIGKILL'); }, 2000);
  backendProcess = null;
}

function waitForBackend(timeout = 15000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const check = () => {
      const http = require('http');
      const req = http.get(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`, (res) => {
        let data = '';
        res.on('data', (c) => data += c);
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            resolve(json.status === 'healthy');
          } catch { resolve(false); }
        });
      });
      req.on('error', () => {
        if (Date.now() - start < timeout) setTimeout(check, 500);
        else resolve(false);
      });
      req.setTimeout(2000, () => { req.destroy(); });
    };
    check();
  });
}

function createMainWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    x: Math.floor((width - 1280) / 2),
    y: Math.floor((height - 800) / 2),
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: true,
    vibrancy: 'under-window',
    visualEffectState: 'active',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });

  mainWindow.loadURL(FRONTEND_URL);

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  return mainWindow;
}

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'tray.png');
  let trayIcon;
  if (fs.existsSync(iconPath)) {
    trayIcon = Tray.generateImageFromPath(iconPath);
  } else {
    trayIcon = Tray.generateImageFromBlank({ width: 16, height: 16 });
  }

  tray = new Tray(trayIcon);
  tray.setTooltip('AURA - Nucleus OS');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Mostrar AURA',
      click: () => showWindow(),
    },
    {
      label: 'Ocultar AURA',
      click: () => hideWindow(),
    },
    { type: 'separator' },
    {
      label: 'Estado del Backend',
      click: () => {
        tray.popUpContextMenu();
      },
    },
    { type: 'separator' },
    {
      label: 'Salida',
      click: () => { isQuitting = true; app.quit(); },
    },
  ]);

  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow && mainWindow.isVisible()) hideWindow();
    else showWindow();
  });

  tray.on('right-click', () => {
    tray.popUpContextMenu();
  });
}

function showWindow() {
  if (!mainWindow) createMainWindow();
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    if (!mainWindow.isVisible()) mainWindow.moveTop();
  }
}

function hideWindow() {
  if (mainWindow && mainWindow.isVisible()) {
    mainWindow.hide();
  }
}

function toggleWindow() {
  if (!mainWindow) { showWindow(); return; }
  if (mainWindow.isVisible()) hideWindow();
  else showWindow();
}

function registerShortcuts() {
  if (shortcutsRegistered) return;
  globalShortcut.register(SHORTCUTS.show, showWindow);
  globalShortcut.register(SHORTCUTS.hide, hideWindow);
  globalShortcut.register(SHORTCUTS.toggle, toggleWindow);
  shortcutsRegistered = true;
}

function unregisterShortcuts() {
  globalShortcut.unregisterAll();
  shortcutsRegistered = false;
}

function setupIPCHandlers() {
  ipcMain.on('aura:show', showWindow);
  ipcMain.on('aura:hide', hideWindow);
  ipcMain.on('aura:toggle', toggleWindow);
  ipcMain.on('aura:get-backend-status', (e) => {
    e.reply('aura:backend-status', {
      running: !!backendProcess,
      port: BACKEND_PORT,
      host: BACKEND_HOST,
    });
  });
  ipcMain.on('aura:restart-backend', () => {
    stopBackend();
    setTimeout(startBackend, 1000);
  });
}

app.whenReady().then(async () => {
  startBackend();
  await waitForBackend();
  createMainWindow();
  createTray();
  registerShortcuts();
  setupIPCHandlers();

  app.setAppUserModelId('com.aura.os.nucleus');
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin' && !isQuitting) {
    return;
  }
  app.quit();
});

app.on('before-quit', () => {
  isQuitting = true;
  unregisterShortcuts();
  stopBackend();
});

app.on('activate', () => {
  if (!mainWindow) createMainWindow();
  else mainWindow.show();
});

app.on('will-quit', () => {
  stopBackend();
});

module.exports = { app, showWindow, hideWindow, toggleWindow };