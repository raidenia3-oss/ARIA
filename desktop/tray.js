const { contextBridge, ipcMain, globalShortcut, screen, shell } = require('electron');
const path = require('path');

function showWindow() {
  const { BrowserWindow } = require('electron');
  const win = BrowserWindow.getAllWindows()[0];
  if (win) win.show();
}

function hideWindow() {
  const { BrowserWindow } = require('electron');
  const win = BrowserWindow.getAllWindows()[0];
  if (win) win.hide();
}

function toggleWindow() {
  const { BrowserWindow } = require('electron');
  const win = BrowserWindow.getAllWindows()[0];
  if (!win) return;
  if (win.isVisible()) win.hide();
  else win.show();
}

module.exports = { showWindow, hideWindow, toggleWindow };