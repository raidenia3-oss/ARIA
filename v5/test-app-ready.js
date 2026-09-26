// Test accessing electron modules after app ready
const electron = require('electron');

console.log('Before app ready:');
console.log('electron.app:', electron.app);
console.log('electron.ipcMain:', electron.ipcMain);

// Try to access the modules
try {
  console.log('electron.app.name:', electron.app?.name);
} catch (e) {
  console.log('Error accessing app.name:', e.message);
}

// Wait for app ready
electron.app.whenReady().then(() => {
  console.log('\nAfter app ready:');
  console.log('electron.app:', electron.app);
  console.log('electron.ipcMain:', electron.ipcMain);
  
  try {
    console.log('electron.app.name:', electron.app?.name);
    console.log('electron.ipcMain.handle:', electron.ipcMain?.handle);
  } catch (e) {
    console.log('Error:', e.message);
  }
  
  // Try creating a window
  try {
    const win = new electron.BrowserWindow({ width: 400, height: 300, show: false });
    console.log('BrowserWindow created:', !!win);
    win.destroy();
  } catch (e) {
    console.log('Error creating window:', e.message);
  }
  
  process.exit(0);
});