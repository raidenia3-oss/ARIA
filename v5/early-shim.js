// Early shim - runs before main script
console.log('=== Early shim running ===');
console.log('require.cache keys:', Object.keys(require.cache));
console.log('process.versions.electron:', process.versions.electron);

// Check if electron module is already in cache
if (require.cache[require.resolve('electron')]) {
  console.log('electron module in cache:', require.cache[require.resolve('electron')].exports);
} else {
  console.log('electron module NOT in cache');
}

// Try to load the built-in electron module using Module._load
const Module = require('module');
try {
  const builtinElectron = Module._load('electron', module, false);
  console.log('Module._load electron:', builtinElectron);
} catch (err) {
  console.log('Module._load error:', err.message);
}

// Try to get the internal binding
try {
  const binding = process.binding('electron');
  console.log('process.binding(electron):', binding);
} catch (err) {
  console.log('process.binding error:', err.message);
}

console.log('=== Early shim done ===');