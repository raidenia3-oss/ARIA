// Check for global electron objects
console.log('global.electron:', global.electron);
console.log('global.app:', global.app);
console.log('global.BrowserWindow:', global.BrowserWindow);
console.log('global.ipcMain:', global.ipcMain);
console.log('process.electron:', process.electron);
console.log('process.binding("electron"):', process.binding('electron'));

// Check all global properties
const electronGlobals = Object.keys(global).filter(k => k.toLowerCase().includes('electron') || k.toLowerCase().includes('app') || k.toLowerCase().includes('browser') || k.toLowerCase().includes('ipc'));
console.log('Electron-related globals:', electronGlobals);