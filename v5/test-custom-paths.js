// Test loading electron with custom module paths
const Module = require('module');

// Create a fake module with no node_modules in paths
const fakeModule = new Module('', null);
fakeModule.paths = ['/fake/path']; // No node_modules

console.log('Fake module paths:', fakeModule.paths);

// Try to load electron with this fake module
try {
  const electron = Module._load('electron', fakeModule, true);
  console.log('Module._load with fake module:', typeof electron, electron);
} catch (e) {
  console.log('Error:', e.message);
}

// Try with the real module but modified paths
const realModule = module;
const originalPaths = realModule.paths;
realModule.paths = ['/fake/path'];

try {
  const electron = Module._load('electron', realModule, true);
  console.log('Module._load with modified paths:', typeof electron, electron);
} catch (e) {
  console.log('Error with modified paths:', e.message);
}

realModule.paths = originalPaths;