// Test requiring electron in a fresh context
const vm = require('vm');

const context = vm.createContext({});
const script = new vm.Script('require("electron")');

try {
  const result = script.runInContext(context);
  console.log('vm result:', result);
} catch (err) {
  console.log('vm error:', err.message);
}

// Try with different require paths
const paths = ['electron', 'electron/main', 'electron/renderer', '@electron/internal', 'electron-internal'];

for (const p of paths) {
  try {
    const result = require(p);
    console.log(`require('${p}'):`, result);
  } catch (err) {
    console.log(`require('${p}') error:`, err.code);
  }
}