// Test requiring built-in Electron modules directly
const app = require('app');
const BrowserWindow = require('browser-window');
const ipcMain = require('ipc-main');

console.log('app:', app);
console.log('BrowserWindow:', BrowserWindow);
console.log('ipcMain:', ipcMain);

app.whenReady().then(() => {
  console.log('App ready');
  const win = new BrowserWindow({ width: 800, height: 600 });
  win.loadURL('about:blank');
});