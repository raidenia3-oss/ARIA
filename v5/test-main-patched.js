// Patch require cache to use Electron's internal modules
delete require.cache[require.resolve('electron')];

const { app, BrowserWindow, ipcMain } = require('electron');

console.log('app:', app);
console.log('BrowserWindow:', BrowserWindow);
console.log('ipcMain:', ipcMain);

app.whenReady().then(() => {
  console.log('App ready');
  const win = new BrowserWindow({ width: 800, height: 600 });
  win.loadURL('about:blank');
});