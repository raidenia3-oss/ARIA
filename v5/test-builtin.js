// Test how to access built-in electron modules
console.log('process.versions.electron:', process.versions.electron);
console.log('process.type:', process.type);
console.log('process.electronBinding:', typeof process.electronBinding);
console.log('process.atomBinding:', typeof process.atomBinding);

// Try to access built-in module via Module._load with different approaches
const Module = require('module');

// Try loading without going through the npm package
try {
  // Clear cache
  delete Module._cache['electron'];
  delete Module._cache[require.resolve('electron')];
  
  // Try to load with isMain=true
  const electron = Module._load('electron', module, true);
  console.log('Module._load with isMain=true:', typeof electron, electron);
} catch (e) {
  console.log('Module._load error:', e.message);
}

// Try to access via internal binding
try {
  const binding = process.binding('electron');
  console.log('process.binding(electron):', binding);
} catch (e) {
  console.log('process.binding error:', e.message);
}

// Check if there's a global electron object
console.log('global.electron:', typeof global.electron);

// Check process._linkedBinding
console.log('process._linkedBinding:', typeof process._linkedBinding);
if (process._linkedBinding) {
  try {
    const binding = process._linkedBinding('electron');
    console.log('_linkedBinding(electron):', binding);
  } catch (e) {
    console.log('_linkedBinding error:', e.message);
  }
}