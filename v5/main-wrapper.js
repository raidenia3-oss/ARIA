const Module = require('module')
const path = require('path')

// Patch Module._nodeModulePaths to exclude the node_modules containing electron package
const electronPkg = require.resolve('electron/package.json')
const electronDir = path.dirname(electronPkg)
const nodeModulesDir = path.dirname(electronDir) // This is the node_modules directory

console.log('[Wrapper] Patching Module._nodeModulePaths to exclude:', nodeModulesDir)

const originalNodeModulePaths = Module._nodeModulePaths
Module._nodeModulePaths = function(from) {
  const paths = originalNodeModulePaths.call(this, from)
  const filtered = paths.filter(p => p !== nodeModulesDir && !p.endsWith(path.sep + 'node_modules' + path.sep + 'electron'))
  if (paths.length !== filtered.length) {
    console.log('[Wrapper] Filtered nodeModulesDir from module paths for:', from)
  }
  return filtered
}

// Also patch global paths
if (Module.globalPaths) {
  const idx = Module.globalPaths.indexOf(nodeModulesDir)
  if (idx >= 0) {
    Module.globalPaths.splice(idx, 1)
    console.log('[Wrapper] Removed nodeModulesDir from Module.globalPaths')
  }
}

// Delete from require cache
delete require.cache[electronPkg]
delete require.cache[require.resolve('electron')]

// Now load the actual main process
console.log('[Wrapper] Loading main process...')
require('./dist-electron/main.js')