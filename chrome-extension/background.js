/* AURA Bridge — background service worker */

const WS_URL = "ws://localhost:48799/aura";
let ws = null;
let reconnectInterval = 3000;

function connect() {
  ws = new WebSocket(WS_URL);
  ws.addEventListener("open", () => {
    console.log("[AURA Bridge] Connected");
  });
  ws.addEventListener("message", (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch (e) {
      console.error("[AURA Bridge] Invalid message", e);
    }
  });
  ws.addEventListener("close", () => {
    setTimeout(connect, reconnectInterval);
  });
  ws.addEventListener("error", () => {
    ws.close();
  });
}

function handleMessage(msg) {
  if (msg.action === "ping") {
    ws.send(JSON.stringify({ action: "pong", source: "chrome" }));
  }
  if (msg.action === "get_tabs") {
    chrome.tabs.query({}, (tabs) => {
      ws.send(JSON.stringify({
        action: "tabs",
        tabs: tabs.map(t => ({ id: t.id, title: t.title, url: t.url }))
      }));
    });
  }
  if (msg.action === "eval_tab") {
    const { tabId, code } = msg;
    chrome.scripting.executeScript({
      target: { tabId },
      func: (c) => {
        try {
          const result = eval(c);
          return { result: String(result) };
        } catch (e) {
          return { error: String(e) };
        }
      },
      args: [code]
    }, (results) => {
      ws.send(JSON.stringify({ action: "eval_result", tabId, result: results?.[0]?.result }));
    });
  }
}

connect();
