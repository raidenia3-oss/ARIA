// Check process.mainModule
console.log('process.mainModule:', process.mainModule);
console.log('process.mainModule.exports:', process.mainModule?.exports);
console.log('process.mainModule.filename:', process.mainModule?.filename);
console.log('process.mainModule.paths:', process.mainModule?.paths);

// Check module
console.log('\nmodule:', module);
console.log('module.exports:', module.exports);
console.log('module.filename:', module.filename);
console.log('module.paths:', module.paths);

// Check require.cache
console.log('\nrequire.cache keys:');
for (const key of Object.keys(require.cache)) {
  if (key.includes('electron')) {
    console.log('  ', key);
  }
}