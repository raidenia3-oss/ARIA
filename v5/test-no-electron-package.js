// test-no-electron-package.js - Test main process without electron package in NODE_PATH
const { spawn } = require('child_process');
const path = require('path');

// Create temp node_modules without electron package
const fs = require('fs');
const tempDir = path.join(__dirname, 'temp-node-modules-no-electron');

try {
  if (fs.existsSync(tempDir)) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
} catch (err) {
  console.log('Could not remove temp dir:', err.message);
}

try {
  fs.mkdirSync(tempDir, { recursive: true });
} catch (err) {
  console.log('Could not create temp dir:', err.message);
}

// Copy all node_modules except electron
const nodeModules = path.join(__dirname, 'node_modules');
let entries = [];
try {
  entries = fs.readdirSync(nodeModules);
} catch (err) {
  console.log('Could not read node_modules:', err.message);
}

for (const entry of entries) {
  if (entry !== 'electron') {
    try {
      fs.cpSync(path.join(nodeModules, entry), path.join(tempDir, entry), { recursive: true });
    } catch (err) {
      console.log(`Could not copy ${entry}:`, err.message);
    }
  }
}

console.log('Temp node_modules created at:', tempDir);
try {
  console.log('Entries:', fs.readdirSync(tempDir));
} catch (err) {
  console.log('Could not list temp dir:', err.message);
}

// Spawn electron with custom NODE_PATH
const electronBinary = path.join(__dirname, 'node_modules', 'electron', 'dist', 'electron.exe');
const mainScript = path.join(__dirname, 'dist-electron', 'main.js');

console.log('Spawning:', electronBinary, mainScript);

const child = spawn(electronBinary, [mainScript], {
  env: { ...process.env, NODE_PATH: tempDir },
  stdio: 'inherit'
});

child.on('error', (err) => {
  console.error('Spawn error:', err);
});

child.on('spawn', () => {
  console.log('Child process spawned');
});

child.stdout?.on('data', (data) => {
  console.log('STDOUT:', data.toString());
});

child.stderr?.on('data', (data) => {
  console.error('STDERR:', data.toString());
});

child.on('close', (code, signal) => {
  console.log(`Child process exited with code ${code}, signal ${signal}`);
});