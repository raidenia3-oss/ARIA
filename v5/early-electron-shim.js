// early-electron-shim.js - Load built-in electron module early
const Module = require('module');

console.log('[early-electron-shim] Loading built-in electron module...');

// Try to load the built-in electron module using the main module as parent
// This should trigger Electron's module loader
try {
  const builtinElectron = Module._load('electron', process.mainModule, true);
  console.log('[early-electron-shim] Module._load result:', typeof builtinElectron, builtinElectron?.app ? 'has app' : 'no app');
  
  if (builtinElectron && typeof builtinElectron === 'object' && builtinElectron.app) {
    // Success! Cache it
    require.cache[require.resolve('electron')] = { exports: builtinElectron };
    console.log('[early-electron-shim] Built-in electron module cached');
  } else {
    console.log('[early-electron-shim] Built-in module not available yet, will try lazy loading');
    
    // Create a proxy that will lazy-load the built-in module
    const electronProxy = new Proxy({}, {
      get(target, prop) {
        try {
          const builtin = Module._load('electron', process.mainModule, true);
          if (builtin && builtin[prop]) {
            return builtin[prop];
          }
        } catch (err) {}
        return undefined;
      },
      ownKeys() {
        try {
          const builtin = Module._load('electron', process.mainModule, true);
          if (builtin) {
            return Object.keys(builtin);
          }
        } catch (err) {}
        return [];
      }
    });
    
    require.cache[require.resolve('electron')] = { exports: electronProxy };
    console.log('[early-electron-shim] Electron proxy cached');
  }
} catch (err) {
  console.log('[early-electron-shim] Error:', err.message);
}