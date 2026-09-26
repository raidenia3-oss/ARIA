"use strict";
const electron = require("electron");
const api = {
  chatSend: (message) => electron.ipcRenderer.invoke("chat:send", message),
  skillsLoad: () => electron.ipcRenderer.invoke("skills:load"),
  settingsGet: () => electron.ipcRenderer.invoke("settings:get"),
  settingsSet: (settings) => electron.ipcRenderer.invoke("settings:set", settings),
  systemStatus: () => electron.ipcRenderer.invoke("system:status"),
  windowMinimize: () => electron.ipcRenderer.invoke("window:minimize"),
  windowMaximize: () => electron.ipcRenderer.invoke("window:maximize"),
  windowClose: () => electron.ipcRenderer.invoke("window:close"),
  windowSetOpacity: (opacity) => electron.ipcRenderer.invoke("window:opacity", opacity),
  onChatStream: (callback) => {
    const listener = (_event, data) => callback(_event, data);
    electron.ipcRenderer.on("chat:stream", listener);
    return () => electron.ipcRenderer.removeListener("chat:stream", listener);
  }
};
electron.contextBridge.exposeInMainWorld("electronAPI", api);
