const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aura', {
  show: () => ipcRenderer.invoke('aura:show'),
  hide: () => ipcRenderer.invoke('aura:hide'),
  toggle: () => ipcRenderer.invoke('aura:toggle'),
  onBackendStatus: (callback) => ipcRenderer.on('aura:backend-status', (_event, status) => callback(status)),
  getBackendStatus: () => ipcRenderer.invoke('aura:get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('aura:restart-backend'),
});