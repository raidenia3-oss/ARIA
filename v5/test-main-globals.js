// Test what's available in Electron main process
console.log('=== Testing Electron main process globals ===');
console.log('global.app:', typeof global.app);
console.log('global.BrowserWindow:', typeof global.BrowserWindow);
console.log('global.ipcMain:', typeof global.ipcMain);
console.log('global.shell:', typeof global.shell);
console.log('global.Tray:', typeof global.Tray);
console.log('global.Menu:', typeof global.Menu);
console.log('global.nativeImage:', typeof global.nativeImage);
console.log('global.powerMonitor:', typeof global.powerMonitor);

// Check process
console.log('process.app:', typeof process.app);
console.log('process.BrowserWindow:', typeof process.BrowserWindow);

// Check if electron is available as a global
console.log('global.electron:', typeof global.electron);

// Try require without cache
delete require.cache[require.resolve('electron')];
const electron = require('electron');
console.log('require(electron):', electron);
console.log('typeof electron:', typeof electron);
if (electron && typeof electron === 'object') {
  console.log('electron.app:', electron.app);
  console.log('electron.ipcMain:', electron.ipcMain);
}