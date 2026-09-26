// check-cache.js - Check require cache at startup
console.log('=== Require cache at startup ===');
Object.keys(require.cache).forEach(key => {
  console.log(key);
});

console.log('\n=== Module paths ===');
module.paths.forEach(p => console.log(p));

console.log('\n=== process.mainModule ===');
console.log('id:', process.mainModule.id);
console.log('path:', process.mainModule.path);
console.log('paths:', process.mainModule.paths);