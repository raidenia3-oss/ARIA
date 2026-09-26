// Test @electron/remote in main process
const { remote } = require('@electron/remote');

console.log('remote:', remote);
console.log('remote.app:', remote.app);
console.log('remote.BrowserWindow:', remote.BrowserWindow);

if (remote.app) {
  remote.app.whenReady().then(() => {
    console.log('App ready via remote');
    const win = new remote.BrowserWindow({ width: 800, height: 600 });
    win.loadFile('index.html');
  });
}