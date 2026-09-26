// Electron main entry - patches require before loading main
// This file is run directly by electron binary

// Patch Module._load to return proper electron module
const Module = require('module');
const originalLoad = Module._load;

Module._load = function(request, parent, isMain) {
  if (request === 'electron') {
    // Return a proper electron module with all main process APIs
    // These are available in the Electron main process
    const electronModule = {};
    
    // The actual Electron modules are available through the built-in module
    // We need to access them. In Electron main process, they should be available
    // through the global electron object or process binding.
    
    // Try to get the real electron module
    let realElectron = null;
    try {
      // Try to access via process binding (older Electron)
      if (process.electronBinding) {
        realElectron = process.electronBinding('electron');
      }
    } catch (e) {
      // ignore
    }
    
    // If we couldn't get it via binding, try to get it from the global scope
    // In Electron main process, the modules might be available as globals
    if (!realElectron) {
      // Check if modules are available as globals
      const modules = [
        'app', 'BrowserWindow', 'ipcMain', 'shell', 'Tray', 'Menu',
        'nativeImage', 'powerMonitor', 'dialog', 'globalShortcut',
        'screen', 'session', 'webContents', 'protocol', 'net',
        'systemPreferences', 'desktopCapturer', 'clipboard', 'crashReporter'
      ];
      
      let hasGlobals = false;
      for (const mod of modules) {
        if (global[mod] || process[mod]) {
          hasGlobals = true;
          break;
        }
      }
      
      if (hasGlobals) {
        // Use globals
        for (const mod of modules) {
          Object.defineProperty(electronModule, mod, {
            get() {
              return global[mod] || process[mod];
            },
            configurable: true,
            enumerable: true
          });
        }
        
        Module._cache['electron'] = electronModule;
        return electronModule;
      }
    }
    
    // If we have realElectron from binding, use it
    if (realElectron) {
      Module._cache['electron'] = realElectron;
      return realElectron;
    }
    
    // Last resort: create a module that throws helpful errors
    // This should not happen in a real Electron main process
    const modules = [
      'app', 'BrowserWindow', 'ipcMain', 'shell', 'Tray', 'Menu',
      'nativeImage', 'powerMonitor', 'dialog', 'globalShortcut',
      'screen', 'session', 'webContents', 'protocol', 'net',
      'systemPreferences', 'desktopCapturer', 'clipboard', 'crashReporter'
    ];
    
    for (const mod of modules) {
      Object.defineProperty(electronModule, mod, {
        get() {
          throw new Error(`Electron '${mod}' not available. This should not happen in Electron main process.`);
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

// Now load the actual main code
require('./dist-electron/main.js');