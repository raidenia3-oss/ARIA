// electron-shim.js - Patch electron module to use internal Electron APIs
const Module = require('module');
const originalRequire = Module.prototype.require;

Module.prototype.require = function(id) {
  if (id === 'electron') {
    // Try to get the internal electron module from the main module
    if (process.mainModule && process.mainModule !== this) {
      try {
        return process.mainModule.require('electron');
      } catch (e) {}
    }
    
    // Return a minimal object with the main process APIs
    // These should be available as built-ins in Electron main process
    const internalElectron = {};
    const modules = [
      'app', 'BrowserWindow', 'ipcMain', 'shell', 'Tray', 
      'Menu', 'nativeImage', 'powerMonitor'
    ];
    
    for (const mod of modules) {
      try {
        internalElectron[mod] = originalRequire.call(this, mod);
      } catch (e) {
        // Module not available as built-in
      }
    }
    
    if (Object.keys(internalElectron).length > 0) {
      return internalElectron;
    }
  }
  
  return originalRequire.call(this, id);
};