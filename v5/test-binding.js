// Test if we can access built-in modules directly
console.log('Testing direct access...');

// Try process.electronBinding
if (process.electronBinding) {
  console.log('process.electronBinding exists');
  try {
    const electron = process.electronBinding('electron');
    console.log('electronBinding(electron):', electron);
  } catch (e) {
    console.log('electronBinding error:', e.message);
  }
} else {
  console.log('process.electronBinding: undefined');
}

// Try process.atomBinding (older Electron versions)
if (process.atomBinding) {
  console.log('process.atomBinding exists');
  try {
    const electron = process.atomBinding('electron');
    console.log('atomBinding(electron):', electron);
  } catch (e) {
    console.log('atomBinding error:', e.message);
  }
} else {
  console.log('process.atomBinding: undefined');
}

// Try Module._load with different approaches
const Module = require('module');
try {
  // Try loading with isMain=true
  const electron = Module._load('electron', module, true);
  console.log('Module._load with isMain=true:', electron);
} catch (e) {
  console.log('Module._load isMain error:', e.message);
}

// Check internal binding
try {
  const internal = process.binding('electron');
  console.log('process.binding(electron):', internal);
} catch (e) {
  console.log('process.binding error:', e.message);
}