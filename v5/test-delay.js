// Test if electron modules become available after a delay
const electron = require('electron');

console.log('Immediate:');
console.log('electron:', electron);
console.log('typeof electron:', typeof electron);

if (typeof electron === 'object' && electron !== null) {
  console.log('electron.app:', electron.app);
  console.log('electron.ipcMain:', electron.ipcMain);
}

// Wait a bit
setTimeout(() => {
  console.log('\nAfter 100ms:');
  console.log('electron:', require('electron'));
  console.log('electron.app:', require('electron').app);
  console.log('electron.ipcMain:', require('electron').ipcMain);
}, 100);

// Wait for app ready
setTimeout(() => {
  console.log('\nAfter 500ms:');
  const e = require('electron');
  console.log('electron:', e);
  console.log('electron.app:', e.app);
  console.log('electron.ipcMain:', e.ipcMain);
}, 500);