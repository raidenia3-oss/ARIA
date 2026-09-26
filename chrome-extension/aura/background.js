// AURA - Background Service Worker
const API_BASE = "https://aura-web-chi-seven.vercel.app/api";

chrome.runtime.onInstalled.addListener(() => {
  console.log("AURA Extension installed");
});

// Escuchar mensajes del content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "UPDATE_EMOTION") {
    fetch(`${API_BASE}/avatar/emotion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ emotion: msg.emotion, platform: "extension" }),
    });
  }
  if (msg.type === "GET_SYNC") {
    fetch(`${API_BASE}/sync`)
      .then((r) => r.json())
      .then(sendResponse);
    return true;
  }
});

// Sincronización periódica
setInterval(() => {
  chrome.runtime.sendMessage({ type: "GET_SYNC" });
}, 60000);
