// Simple test - standard electron main process
const { app, BrowserWindow, ipcMain } = require('electron');

console.log('app:', typeof app);
console.log('BrowserWindow:', typeof BrowserWindow);
console.log('ipcMain:', typeof ipcMain);

if (!app || !ipcMain) {
  console.error('FAILED: electron modules not available');
  process.exit(1);
}

console.log('SUCCESS: electron modules available');

app.whenReady().then(() => {
  console.log('App ready');
  const win = new BrowserWindow({ width: 400, height: 300, show: false });
  console.log('Window created');
  win.destroy();
  app.quit();
});