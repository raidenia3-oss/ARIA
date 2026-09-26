// electron-builtin-shim.js - Load the built-in electron module
const Module = require('module');

// Save original require
const originalRequire = Module.prototype.require;

// Override require to intercept electron module
Module.prototype.require = function(id) {
  if (id === 'electron' || id === 'electron/main' || id === 'electron/renderer') {
    // Try to load the built-in electron module
    try {
      // Use Module._load with the main module as parent to trigger Electron's module loader
      const builtinElectron = Module._load('electron', process.mainModule, true);
      if (builtinElectron && typeof builtinElectron === 'object' && builtinElectron.app) {
        // Cache it
        require.cache[require.resolve('electron')] = { exports: builtinElectron };
        return builtinElectron;
      }
    } catch (err) {
      // Ignore
    }
    
    // Fallback: create a minimal electron module with the main process APIs
    // These will be populated when the Electron binary initializes
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
          
          // Try to get from global (might be set by Electron binary)
          if (global[mod]) {
            return global[mod];
          }
          
          // Try to get from process
          if (process[mod]) {
            return process[mod];
          }
          
          return undefined;
        },
        configurable: true,
        enumerable: true
      });
    }
    
    // Cache it
    require.cache[require.resolve('electron')] = { exports: electronModule };
    return electronModule;
  }
  
  return originalRequire.call(this, id);
};

console.log('[electron-builtin-shim] Loaded');