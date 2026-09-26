// Electron launcher - patches require to use built-in electron module
// Run with: electron electron-launcher.js

const Module = require('module');
const originalLoad = Module._load;

// Track if we've patched
let patched = false;

Module._load = function(request, parent, isMain) {
  if (request === 'electron' && !patched) {
    patched = true;
    
    // In Electron main process, try to get the built-in module
    // The built-in module should be available via the internal binding
    try {
      // Try to access the built-in electron module
      // This works in Electron main process
      const binding = process.electronBinding?.('electron');
      if (binding) {
        Module._cache['electron'] = binding;
        return binding;
      }
    } catch (e) {
      // ignore
    }
    
    // Fallback: create a module that lazily loads from the real electron
    // when properties are accessed
    const electronModule = {};
    const modules = [
      'app', 'BrowserWindow', 'ipcMain', 'shell', 'Tray', 'Menu', 
      'nativeImage', 'powerMonitor', 'dialog', 'globalShortcut', 
      'screen', 'session', 'webContents', 'protocol', 'net', 
      'systemPreferences', 'desktopCapturer', 'clipboard', 'crashReporter'
    ];
    
    for (const mod of modules) {
      Object.defineProperty(electronModule, mod, {
        get() {
          try {
            // Try to get from the real electron module (which should be the built-in one now)
            const realElectron = originalLoad.call(Module, 'electron', parent, false);
            if (realElectron && typeof realElectron === 'object' && realElectron[mod]) {
              return realElectron[mod];
            }
          } catch (e) {
            // ignore
          }
          // Try global
          if (global[mod]) return global[mod];
          // Return stub
          return (...args) => {
            throw new Error(`Electron '${mod}' not available`);
          };
        },
        configurable: true,
        enumerable: true
      });
    }
    
    Module._cache['electron'] = electronModule;
    return electronModule;
  }
  
  return originalLoad.apply(this, arguments);
};

// Now load the actual main script
require('./dist-electron/main.js');