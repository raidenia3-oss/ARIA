// remove-electron-package.js - Remove electron package from module paths
// This must run before any other code

// Remove electron from module paths
const originalPaths = module.constructor.prototype.paths;
Object.defineProperty(module.constructor.prototype, 'paths', {
  get() {
    return originalPaths.filter(p => !p.includes('electron'));
  },
  configurable: true
});

// Also remove from current module paths
module.paths = module.paths.filter(p => !p.includes('electron'));

// Remove electron from require cache
Object.keys(require.cache).forEach(key => {
  if (key.includes('electron')) {
    delete require.cache[key];
  }
});

console.log('[remove-electron-package] Electron package removed from module paths');