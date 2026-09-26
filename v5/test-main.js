console.log('Testing electron require...');
const electron = require('electron');
console.log('electron:', electron);
console.log('electron.app:', electron?.app);
console.log('electron.ipcMain:', electron?.ipcMain);
console.log('process.type:', process.type);
console.log('process.versions.electron:', process.versions.electron);