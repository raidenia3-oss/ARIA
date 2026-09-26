// Test all possible ways to access electron modules
console.log('=== Testing all possible access methods ===');

// 1. require('electron')
try {
  const e = require('electron');
  console.log('1. require(electron):', typeof e, e);
} catch (err) {
  console.log('1. require(electron): ERROR', err.message);
}

// 2. process.mainModule.require('electron')
try {
  const e = process.mainModule.require('electron');
  console.log('2. process.mainModule.require(electron):', typeof e, e);
} catch (err) {
  console.log('2. process.mainModule.require(electron): ERROR', err.message);
}

// 3. module.require('electron')
try {
  const e = module.require('electron');
  console.log('3. module.require(electron):', typeof e, e);
} catch (err) {
  console.log('3. module.require(electron): ERROR', err.message);
}

// 4. Module._load('electron', module, true)
try {
  const Module = require('module');
  const e = Module._load('electron', module, true);
  console.log('4. Module._load(electron, module, true):', typeof e, e);
} catch (err) {
  console.log('4. Module._load: ERROR', err.message);
}

// 5. Check global for any electron-related properties
console.log('\n5. Global properties containing "electron":');
for (const key of Object.keys(global)) {
  if (key.toLowerCase().includes('electron') || key.toLowerCase().includes('app') || key.toLowerCase().includes('browser') || key.toLowerCase().includes('ipc')) {
    console.log(`  global.${key}:`, typeof global[key]);
  }
}

// 6. Check process for any electron-related properties
console.log('\n6. Process properties containing "electron":');
for (const key of Object.keys(process)) {
  if (key.toLowerCase().includes('electron') || key.toLowerCase().includes('app') || key.toLowerCase().includes('browser') || key.toLowerCase().includes('ipc')) {
    console.log(`  process.${key}:`, typeof process[key]);
  }
}

// 7. Check if there's a global electron object
console.log('\n7. global.electron:', global.electron);

// 8. Try to access via process.binding
console.log('\n8. process.binding:');
try {
  const bindings = process.binding('electron');
  console.log('  process.binding(electron):', bindings);
} catch (err) {
  console.log('  process.binding(electron): ERROR', err.message);
}

// 9. Check Module._cache
console.log('\n9. Module._cache[electron]:', require('module')._cache['electron']);

// 10. Try require.resolve
console.log('\n10. require.resolve(electron):');
try {
  console.log('  ', require.resolve('electron'));
} catch (err) {
  console.log('  ERROR', err.message);
}