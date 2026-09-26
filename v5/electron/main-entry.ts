// Electron main entry point - loads shim first, then actual main
// This file is the entry point for vite-plugin-electron

// Load the electron shim first - this must happen before any other electron imports
import './electron-shim.js';

// Now import the actual main process code
import './main.js';