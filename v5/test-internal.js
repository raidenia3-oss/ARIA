// Test all possible internal electron modules
const internalModules = [
  '@electron/internal/main',
  '@electron/internal/renderer',
  'electron/main',
  'electron/renderer',
  'electron/common',
  'internal/electron',
  'internal/electron/main',
  'internal/electron/renderer',
];

for (const mod of internalModules) {
  try {
    const m = require(mod);
    console.log(`${mod}:`, typeof m, m);
  } catch (e) {
    console.log(`${mod}: NOT FOUND`);
  }
}

// Try process._linkedBinding
if (process._linkedBinding) {
  const bindings = [
    'electron',
    'electron_common',
    'electron_main',
    'electron_renderer',
    'atom',
    'atom_common',
    'atom_main',
    'atom_renderer',
  ];
  
  for (const binding of bindings) {
    try {
      const b = process._linkedBinding(binding);
      console.log(`_linkedBinding('${binding}'):`, typeof b, b);
    } catch (e) {
      console.log(`_linkedBinding('${binding}'): NOT FOUND`);
    }
  }
}