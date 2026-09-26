const { globalShortcut } = require('electron');

const SHORTCUTS = {
  show: 'Ctrl+Alt+A',
  hide: 'Ctrl+Alt+H',
  toggle: 'Ctrl+Alt+T',
};

let registered = false;

function registerAll(handlers) {
  if (registered) return;
  globalShortcut.register(SHORTCUTS.show, handlers.show);
  globalShortcut.register(SHORTCUTS.hide, handlers.hide);
  globalShortcut.register(SHORTCUTS.toggle, handlers.toggle);
  registered = true;
}

function unregisterAll() {
  globalShortcut.unregisterAll();
  registered = false;
}

function isRegistered() {
  return registered;
}

module.exports = { SHORTCUTS, registerAll, unregisterAll, isRegistered };