/**
 * AURA Frameless & Translucent Window Manager (Bloque 59).
 *
 * Creates and manages the floating, frameless, translucent window
 * that renders the 3D Nucleus visualizer over any active application.
 */

const { BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');

const WINDOW_DEFAULTS = {
  width: 1280,
  height: 800,
  frame: false,
  transparent: true,
  backgroundColor: '#00000000',
  hasShadow: true,
  alwaysOnTop: false,
  skipTaskbar: false,
  resizable: true,
  minimizable: true,
  maximizable: true,
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: false,
  },
};

function createMainWindow(extraOpts = {}) {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  const win = new BrowserWindow({
    ...WINDOW_DEFAULTS,
    ...extraOpts,
    x: extraOpts.x ?? Math.floor((width - WINDOW_DEFAULTS.width) / 2),
    y: extraOpts.y ?? Math.floor((height - WINDOW_DEFAULTS.height) / 2),
  });

  const frontendUrl = process.env.AURA_FRONTEND_URL || 'http://localhost:8000/dashboard';
  win.loadURL(frontendUrl);

  // Window controls via IPC
  ipcMain.on('window:minimize', () => win.minimize());
  ipcMain.on('window:maximize', () => {
    if (win.isMaximized()) win.unmaximize();
    else win.maximize();
  });
  ipcMain.on('window:close', () => win.close());
  ipcMain.on('window:set-always-on-top', (_e, flag) => win.setAlwaysOnTop(flag));
  ipcMain.on('window:set-opacity', (_e, opacity) => win.setOpacity(Math.max(0.1, Math.min(1, opacity))));

  return win;
}

function makeFloatMode(win) {
  win.setAlwaysOnTop(true);
  win.setOpacity(0.85);
  win.setSkipTaskbar(true);
}

function makeWindowMode(win) {
  win.setAlwaysOnTop(false);
  win.setOpacity(1.0);
  win.setSkipTaskbar(false);
}

module.exports = { createMainWindow, makeFloatMode, makeWindowMode, WINDOW_DEFAULTS };