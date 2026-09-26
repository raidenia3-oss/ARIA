// Debug what's available in Electron main process
console.log('process.versions:', process.versions);
console.log('process.mainModule:', process.mainModule);
console.log('module:', module);
console.log('require.cache keys:', Object.keys(require.cache).filter(k => k.includes('electron')));