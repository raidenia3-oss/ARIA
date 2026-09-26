// Test requiring from process.mainModule
console.log('Testing process.mainModule.require("electron")');
try {
  const e = process.mainModule.require('electron');
  console.log('Result:', e);
} catch (err) {
  console.log('Error:', err.message);
}

console.log('\nTesting process.mainModule.require("app")');
try {
  const app = process.mainModule.require('app');
  console.log('app:', app);
} catch (err) {
  console.log('Error:', err.message);
}