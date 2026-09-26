// custom-resolver.js - Patch Module._resolveFilename to ignore electron package
const Module = require('module');
const originalResolveFilename = Module._resolveFilename;

Module._resolveFilename = function(request, parent, isMain, options) {
  if (request === 'electron' || request === 'electron/main' || request === 'electron/renderer') {
    // Try to resolve as built-in module
    try {
      return originalResolveFilename.call(this, request, parent, isMain, options);
    } catch (err) {
      // If not found, throw a custom error to trigger Electron's module loader
      throw new Error(`Electron built-in module '${request}' not found`);
    }
  }
  return originalResolveFilename.call(this, request, parent, isMain, options);
};

console.log('[custom-resolver] Module._resolveFilename patched');