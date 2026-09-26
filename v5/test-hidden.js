// Check all process properties for electron modules
console.log('=== All process properties ===');
const props = Object.getOwnPropertyNames(process);
for (const prop of props) {
  const desc = Object.getOwnPropertyDescriptor(process, prop);
  if (desc && (desc.value !== undefined || desc.get)) {
    try {
      const val = process[prop];
      if (val && typeof val === 'object') {
        const keys = Object.keys(val);
        if (keys.some(k => k.toLowerCase().includes('app') || k.toLowerCase().includes('browser') || k.toLowerCase().includes('ipc') || k.toLowerCase().includes('window'))) {
          console.log(`process.${prop}:`, typeof val, keys.slice(0, 10));
        }
      }
    } catch (e) {
      // ignore
    }
  }
}

// Check global
console.log('\n=== All global properties ===');
const globalProps = Object.getOwnPropertyNames(global);
for (const prop of globalProps) {
  try {
    const val = global[prop];
    if (val && typeof val === 'object') {
      const keys = Object.keys(val);
      if (keys.some(k => k.toLowerCase().includes('app') || k.toLowerCase().includes('browser') || k.toLowerCase().includes('ipc') || k.toLowerCase().includes('window'))) {
        console.log(`global.${prop}:`, typeof val, keys.slice(0, 10));
      }
    }
  } catch (e) {
    // ignore
  }
}