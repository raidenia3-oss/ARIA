"use strict";

const BACKEND_URL = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/api/mobile/sync/chrome-ext";
const RECONNECT_INTERVAL = 5000;

let ws = null;
let deviceId = null;
let authToken = null;
let enabled = false;
let allowedSites = [];
let reconnectTimer = null;
let currentTaskId = null;
let currentAction = null;

async function init() {
  const stored = await chrome.storage.local.get(["deviceId", "authToken", "enabled", "allowedSites"]);
  deviceId = stored.deviceId || crypto.randomUUID();
  authToken = stored.authToken || null;
  enabled = stored.enabled ?? false;
  allowedSites = stored.allowedSites || [];
  await chrome.storage.local.set({ deviceId });
  if (enabled) connectWS();
}

function connectWS() {
  if (ws) ws.close();
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token: authToken || "extension" }));
    updateStatus("connected");
  };
  ws.onmessage = handleWSMessage;
  ws.onclose = () => {
    updateStatus("disconnected");
    if (enabled) reconnectTimer = setTimeout(connectWS, RECONNECT_INTERVAL);
  };
  ws.onerror = (e) => {
    updateStatus("error");
  };
}

function updateStatus(status) {
  chrome.runtime.sendMessage({ type: "aura_status", status });
  chrome.action.setIcon({ path: `icons/icon48-${status === "connected" ? "on" : "off"}.png` });
}

function handleWSMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === "ping") {
    ws.send(JSON.stringify({ type: "pong" }));
    return;
  }
  if (msg.type === "command") {
    handleCommand(msg.action, msg.data, msg.commandId);
  }
}

async function isAllowed(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname;
    return allowedSites.some(s => {
      try { return new URL(s).hostname === host; } catch { return host === s; }
    });
  } catch {
    return false;
  }
}

async function handleCommand(action, data, commandId) {
  if (!enabled) return;
  if (currentAction) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ commandId, action, status: "error", error: "busy" }));
    }
    return;
  }
  let result = { commandId, action, status: "ok" };
  currentAction = action;

  try {
    switch (action) {
      case "extension_status":
        result.data = { enabled, status: "connected", deviceId, allowedSites };
        break;
      case "active_tab": {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        result.data = { tabId: tab.id, url: tab.url, title: tab.title };
        break;
      }
      case "read_visible": {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!await isAllowed(tab.url)) {
          result.status = "error"; result.error = "site_not_allowed";
          break;
        }
        const response = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => document.body.innerText.slice(0, 5000),
        });
        result.data = { text: response[0].result, tabId: tab.id, url: tab.url };
        break;
      }
      case "open_url": {
        const url = data.url;
        if (!url || !await isAllowed(url)) {
          result.status = "error"; result.error = "url_not_allowed";
          break;
        }
        const tab = await chrome.tabs.create({ url, active: true });
        result.data = { tabId: tab.id, url: tab.url };
        break;
      }
      case "click": {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!await isAllowed(tab.url)) {
          result.status = "error"; result.error = "site_not_allowed";
          break;
        }
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector) => { document.querySelector(selector)?.click(); },
          args: [data.selector],
        });
        result.data = { tabId: tab.id, selector: data.selector };
        break;
      }
      case "type": {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!await isAllowed(tab.url)) {
          result.status = "error"; result.error = "site_not_allowed";
          break;
        }
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (selector, value) => { const el = document.querySelector(selector); if (el) el.value = value; },
          args: [data.selector, data.value],
        });
        result.data = { tabId: tab.id, selector: data.selector };
        break;
      }
      case "screenshot": {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!await isAllowed(tab.url)) {
          result.status = "error"; result.error = "site_not_allowed";
          break;
        }
        const img = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
        result.data = { dataURL: img, tabId: tab.id };
        break;
      }
      case "stop":
        currentAction = null;
        result.data = { stopped: true };
        break;
      default:
        result.status = "error"; result.error = "unknown_action";
    }
  } catch (err) {
    result.status = "error"; result.error = err.message;
  } finally {
    currentAction = null;
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(result));
  }
}

function toggleEnabled() {
  enabled = !enabled;
  chrome.storage.local.set({ enabled });
  if (enabled) connectWS(); else { if (reconnectTimer) clearTimeout(reconnectTimer); if (ws) ws.close(); }
  updateStatus(enabled ? "connecting" : "disabled");
}

function setAllowedSites(sites) {
  allowedSites = sites;
  chrome.storage.local.set({ allowedSites });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "toggle_enabled") toggleEnabled();
  if (msg.type === "get_state") sendResponse({ enabled, status: ws?.readyState === WebSocket.OPEN ? "connected" : "disconnected", currentAction });
  if (msg.type === "set_sites") setAllowedSites(msg.sites);
  if (msg.type === "run_action") {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "command", action: msg.action, data: msg.data }));
    } else {
      sendResponse({ status: "error", error: "not_connected" });
    }
    return true;
  }
});

init();
