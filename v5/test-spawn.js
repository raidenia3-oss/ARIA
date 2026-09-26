// Test if electron modules appear after app initialization
const electron = require('electron');

console.log('Before app creation:');
console.log('electron:', typeof electron);

if (typeof electron === 'string') {
  console.log('electron is string (binary path)');
}

// Try to access the real electron module by using the binary directly
// The electron binary is at electron.exe
const { spawnSync } = require('child_process');
const result = spawnSync(electron, ['-e', 'console.log("app:", typeof require("electron").app); console.log("ipcMain:", typeof require("electron").ipcMain);'], { encoding: 'utf8' });
console.log('\nSpawning electron.exe with test script:');
console.log('stdout:', result.stdout);
console.log('stderr:', result.stderr);
console.log('status:', result.status);