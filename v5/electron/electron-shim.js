// Electron built-in module shim - must be loaded FIRST
// This provides the built-in electron modules by accessing them correctly

// In Electron main process, the built-in modules are available via process.electronBinding
// but it's not exposed. Let's try to access them through the internal module system.

// The key insight: when running in Electron main process, the built-in 'electron' module 
// IS available, but the npm package's index.js returns the binary path instead.

// We need to bypass the npm package and get the real built-in module.

// Store original Module._load
const Module = require('module');
const originalLoad = Module._load;

// Flag to prevent recursion
let isLoadingElectron = false;

Module._load = function(request, parent, isMain) {
  if (request === 'electron' && !isLoadingElectron) {
    isLoadingElectron = true;
    try {
      // Try to load the built-in electron module directly
      // In Electron main process, this should work
      const builtin = originalLoad.call(Module, 'electron', parent, false);
      
      // If builtin is a string (binary path), we need to get the actual module
      if (typeof builtin === 'string') {
        // The built-in module should be available in the global context
        // Let's create a proper module object with all main process APIs
        const electronModule = {};
        
        // List of main process modules we need
        const modules = [
          'app', 'BrowserWindow', 'ipcMain', 'shell', 'Tray', 'Menu', 
          'nativeImage', 'powerMonitor', 'dialog', 'globalShortcut', 
          'screen', 'session', 'webContents', 'protocol', 'net', 
          'systemPreferences', 'desktopCapturer', 'clipboard', 'crashReporter'
        ];
        
        // Try to get each module from the built-in binding
        for (const mod of modules) {
          try {
            // In Electron, these are available as properties of the built-in module
            // But since we can't access it directly, we'll use a getter that 
            // tries to access them when needed
            Object.defineProperty(electronModule, mod, {
              get() {
                try {
                  // Try to get from process (set by Electron)
                  if (global[mod]) {
                    return global[mod];
                  }
                  // Try to get from process.electronBinding if available
                  if (process.electronBinding) {
                    const binding = process.electronBinding('electron');
                    if (binding && binding[mod]) {
                      return binding[mod];
                    }
                  }
                } catch (e) {
                  // ignore
                }
                // Return a function that throws helpful error
                return (...args) => {
                  throw new Error(`Electron '${mod}' not available. Ensure running in Electron main process.`);
                };
              },
              configurable: true,
              enumerable: true
            });
          } catch (e) {
            // ignore
          }
        }
        
        // Cache it
        Module._cache['electron'] = electronModule;
        isLoadingElectron = false;
        return electronModule;
      }
      
      isLoadingElectron = false;
      return builtin;
    } catch (e) {
      isLoadingElectron = false;
      // Fallback to original
      return originalLoad.apply(this, arguments);
    }
  }
  
  return originalLoad.apply(this, arguments);
};

console.log('[Shim] Electron shim loaded');