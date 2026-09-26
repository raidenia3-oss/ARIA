// Test electronBinding
console.log('process.electronBinding:', typeof process.electronBinding);
console.log('process.atomBinding:', typeof process.atomBinding);

if (process.electronBinding) {
  try {
    const electron = process.electronBinding('electron');
    console.log('electronBinding(electron):', electron);
    if (electron) {
      console.log('electron.app:', electron.app);
      console.log('electron.ipcMain:', electron.ipcMain);
    }
  } catch (e) {
    console.log('electronBinding error:', e.message);
  }
}

if (process.atomBinding) {
  try {
    const electron = process.atomBinding('electron');
    console.log('atomBinding(electron):', electron);
  } catch (e) {
    console.log('atomBinding error:', e.message);
  }
}

// Try internal module
try {
  const internal = require('internal/electron');
  console.log('internal/electron:', internal);
} catch (e) {
  console.log('internal/electron error:', e.message);
}

// Try @electron/internal
try {
  const internal = require('@electron/internal');
  console.log('@electron/internal:', internal);
} catch (e) {
  console.log('@electron/internal error:', e.message);
}

// Try electron/main
try {
  const main = require('electron/main');
  console.log('electron/main:', main);
} catch (e) {
  console.log('electron/main error:', e.message);
}

// Try electron/renderer
try {
  const renderer = require('electron/renderer');
  console.log('electron/renderer:', renderer);
} catch (e) {
  console.log('electron/renderer error:', e.message);
}