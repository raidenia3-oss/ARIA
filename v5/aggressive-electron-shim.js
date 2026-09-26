// aggressive-electron-shim.js - Patch require cache directly (no electron requires)
const Module = require('module');
const path = require('path');
const fs = require('fs');

// Create the electron module
const electronModule = createElectronModule();

// Patch the require cache for electron
const electronIndexPath = path.join(__dirname, 'node_modules', 'electron', 'index.js');
if (fs.existsSync(electronIndexPath)) {
  require.cache[electronIndexPath] = { exports: electronModule };
}

// Also patch any electron subpath requires
const electronDir = path.join(__dirname, 'node_modules', 'electron');
if (fs.existsSync(electronDir)) {
  const files = fs.readdirSync(electronDir);
  for (const file of files) {
    if (file.endsWith('.js')) {
      const filePath = path.join(electronDir, file);
      require.cache[filePath] = { exports: electronModule };
    }
  }
}

function createElectronModule() {
  const Module = require('module');
  
  const electronModule = {};
  
  const mainProcessModules = [
    'app', 'BrowserWindow', 'ipcMain', 'ipcRenderer', 'shell', 'Tray',
    'Menu', 'nativeImage', 'powerMonitor', 'dialog', 'globalShortcut',
    'screen', 'session', 'webContents', 'protocol', 'net', 'netLog',
    'desktopCapturer', 'crashReporter', 'systemPreferences', 'accessibilitySupport',
    'contextBridge', 'ipcRenderer'
  ];
  
  for (const mod of mainProcessModules) {
    Object.defineProperty(electronModule, mod, {
      get() {
        // Try to get from the built-in module
        try {
          const builtin = Module._load('electron', process.mainModule, true);
          if (builtin && builtin[mod]) {
            return builtin[mod];
          }
        } catch (err) {}
        
        if (global[mod]) return global[mod];
        if (process[mod]) return process[mod];
        
        if (mod === 'app') return createMockApp();
        if (mod === 'BrowserWindow') return createMockBrowserWindow();
        if (mod === 'ipcMain') return createMockIpcMain();
        
        return undefined;
      },
      configurable: true,
      enumerable: true
    });
  }
  
  return electronModule;
}

function createMockApp() {
  const listeners = {};
  return {
    whenReady: () => Promise.resolve(),
    on: (event, listener) => { listeners[event] = listener; },
    quit: () => {},
    getVersion: () => '5.0.0',
    getName: () => 'ARIA OS',
    setName: () => {},
    getPath: () => '/tmp',
    listeners
  };
}

function createMockBrowserWindow() {
  return function MockBrowserWindow(options) {
    return {
      loadFile: () => {},
      loadURL: () => {},
      on: () => {},
      once: () => {},
      show: () => {},
      hide: () => {},
      close: () => {},
      minimize: () => {},
      maximize: () => {},
      unmaximize: () => {},
      isMaximized: () => false,
      setOpacity: () => {},
      webContents: {
        on: () => {},
        openDevTools: () => {},
        setWindowOpenHandler: () => ({ action: 'deny' })
      }
    };
  };
}

function createMockIpcMain() {
  const handlers = {};
  return {
    handle: (channel, handler) => { handlers[channel] = handler; },
    on: () => {},
    removeHandler: (channel) => { delete handlers[channel]; }
  };
}

console.log('[aggressive-electron-shim] Electron module patched in require cache');