// test-main-direct.js - With proper quit
const { app, BrowserWindow, ipcMain } = require('electron');

console.log('app:', app);
console.log('BrowserWindow:', BrowserWindow);
console.log('ipcMain:', ipcMain);

app.whenReady().then(() => {
  console.log('App ready');
  const win = new BrowserWindow({ width: 800, height: 600 });
  win.loadURL('about:blank');
  console.log('Window created');
  
  // Quit after a short delay
  setTimeout(() => {
    console.log('Quitting...');
    app.quit();
  }, 1000);
});