// Test what's available in Electron main process
console.log('process.versions:', process.versions);
console.log('process.type:', process.type);
console.log('process.electronBinding:', typeof process.electronBinding);
console.log('global.electron:', typeof global.electron);
console.log('global.require:', typeof global.require);

// Try to access built-in modules
try {
  const electron = require('electron');
  console.log('require(electron):', electron);
} catch (e) {
  console.log('require(electron) error:', e.message);
}

// Try Module._load
try {
  const Module = require('module');
  const electron = Module._load('electron', module, false);
  console.log('Module._load(electron):', electron);
} catch (e) {
  console.log('Module._load error:', e.message);
}