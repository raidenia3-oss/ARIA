// Clear require cache and try requiring electron
Object.keys(require.cache).forEach(key => {
  if (key.includes('electron')) {
    delete require.cache[key];
  }
});

// Also clear module paths
module.paths = module.paths.filter(p => !p.includes('electron'));

// Try requiring electron again
const e = require('electron');
console.log('electron:', e);
console.log('app:', e.app);
console.log('BrowserWindow:', e.BrowserWindow);