/* AURA Bridge — popup */

const WS_URL = "ws://localhost:48799/aura";
let ws = null;

function connect() {
  ws = new WebSocket(WS_URL);
  ws.addEventListener("open", () => {
    document.getElementById("status").textContent = "Connected";
  });
  ws.addEventListener("close", () => {
    document.getElementById("status").textContent = "Disconnected";
  });
  ws.addEventListener("error", () => {
    document.getElementById("status").textContent = "Error";
  });
}

document.getElementById("sync").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  ws.send(JSON.stringify({ action: "sync_tab", tabId: tab.id, url: tab.url }));
});

document.getElementById("inject").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const div = document.createElement("div");
      div.style.position = "fixed";
      div.style.bottom = "12px";
      div.style.right = "12px";
      div.style.background = "rgba(10,15,30,0.8)";
      div.style.color = "#e6e9f0";
      div.style.padding = "8px";
      div.style.borderRadius = "8px";
      div.style.fontFamily = "sans-serif";
      div.style.fontSize = "12px";
      div.style.zIndex = 2147483647;
      div.textContent = "AURA injected";
      document.body.appendChild(div);
    }
  });
});

document.getElementById("apps").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  ws.send(JSON.stringify({ action: "get_tabs" }));
});

connect();
