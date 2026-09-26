const Module = require('module')
const path = require('path')

// Aggressively patch module resolution for electron
const electronPkg = require.resolve('electron/package.json')
const electronDir = path.dirname(electronPkg)

console.log('[Patch] electronDir:', electronDir)

// Remove from Module.globalPaths
if (Module.globalPaths) {
  const globalIdx = Module.globalPaths.indexOf(electronDir)
  if (globalIdx >= 0) {
    Module.globalPaths.splice(globalIdx, 1)
    console.log('[Patch] Removed from Module.globalPaths')
  }
}

// Remove from current module paths
if (module.paths) {
  const localIdx = module.paths.indexOf(electronDir)
  if (localIdx >= 0) {
    module.paths.splice(localIdx, 1)
    console.log('[Patch] Removed from module.paths')
  }
}

// Remove from all parent module paths
let parent = module.parent
while (parent) {
  if (parent.paths) {
    const idx = parent.paths.indexOf(electronDir)
    if (idx >= 0) {
      parent.paths.splice(idx, 1)
      console.log('[Patch] Removed from parent module.paths')
    }
  }
  parent = parent.parent
}

// Delete from require cache
delete require.cache[electronPkg]
delete require.cache[require.resolve('electron')]

// Override Module.prototype.require to intercept electron
const originalRequire = Module.prototype.require
Module.prototype.require = function(id) {
  if (id === 'electron') {
    console.log('[Patch] Intercepted require(electron)')
    // Try to get the built-in electron module
    // In Electron, the built-in module should be available
    try {
      // This might work if the built-in module is registered under a different name
      return originalRequire.call(this, '@electron/internal/main-process/electron')
    } catch {
      // Fallback: create a minimal shim with the APIs we need
      console.warn('[Patch] Using fallback electron shim')
      return createElectronShim()
    }
  }
  return originalRequire.call(this, id)
}

function createElectronShim() {
  // This is a minimal shim - in reality we need the real Electron APIs
  // For now, throw an error to see if the patch is working
  throw new Error('Electron shim not implemented - need real Electron built-in module')
}