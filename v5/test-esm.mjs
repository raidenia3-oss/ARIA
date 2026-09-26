// Simple test - just import electron and check modules
import { app, BrowserWindow, ipcMain } from 'electron';

console.log('app:', app);
console.log('BrowserWindow:', BrowserWindow);
console.log('ipcMain:', ipcMain);

if (!app || !ipcMain) {
  throw new Error('Modules not loaded');
}
console.log('SUCCESS: All modules loaded');