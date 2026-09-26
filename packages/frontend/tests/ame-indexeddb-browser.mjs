import { chromium } from "playwright";

const FRONTEND_URL = "http://localhost:3000/ame/ame_core";
const BACKEND_URL = "http://127.0.0.1:8000";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  const results = {
    stores: [],
    chatHistoryOnline: 0,
    pendingCreated: false,
    pendingCleared: false,
    noDuplicates: false,
    errors: [],
    logs: [],
  };

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") results.logs.push(msg.text());
    if (msg.type() === "log" && msg.text().includes("DEBUG")) results.logs.push(msg.text());
  });

  try {
    await page.goto("http://localhost:3000", { waitUntil: "networkidle", timeout: 60000 });
    await page.evaluate(() => localStorage.setItem("aura_authenticated", "true"));
    await page.goto(FRONTEND_URL, { waitUntil: "networkidle", timeout: 60000 });
    await sleep(4000);

    console.log("Checking IndexedDB stores...");
    const stores = await page.evaluate(async () => {
      try {
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open("ame-db", 3);
          req.onerror = () => reject(req.error);
          req.onsuccess = () => resolve(req.result);
        });
        return Array.from(db.objectStoreNames);
      } catch (e) {
        return ["ERROR:" + e.message];
      }
    });
    results.stores = stores;
    console.log("Stores:", stores);

    const required = ["ames", "chat", "events", "pending_events", "device_config"];
    const missing = required.filter((s) => !stores.includes(s));
    if (missing.length > 0) {
      results.errors.push(`Missing stores: ${missing.join(", ")}`);
    }

    console.log("Sending online message...");
    const inputSelector = 'input[type="text"]';
    await page.waitForSelector(inputSelector, { timeout: 30000 });
    await page.fill(inputSelector, "hola desde playwright online");
    await page.click('button:has-text("Enviar")');
    await sleep(4000);

    const chatAfterOnline = await page.evaluate(async () => {
      try {
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open("ame-db", 3);
          req.onerror = () => reject(req.error);
          req.onsuccess = () => resolve(req.result);
        });
        const tx = db.transaction("chat", "readonly");
        const store = tx.objectStore("chat");
        return new Promise((resolve, reject) => {
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || []);
          req.onerror = () => reject(req.error);
        });
      } catch (e) {
        return ["ERROR:" + e.message];
      }
    });
    results.chatHistoryOnline = Array.isArray(chatAfterOnline) ? chatAfterOnline.length : 0;
    console.log("Chat messages after online:", results.chatHistoryOnline);

    console.log("Simulating backend offline by intercepting API...");
    await page.route(`http://localhost:8000/**`, async (route) => {
      const headers = route.request().headers();
      const isWsUpgrade = headers["upgrade"] === "websocket" || headers["connection"]?.includes("upgrade");
      if (isWsUpgrade) {
        route.fulfill({ status: 403, contentType: "text/plain", body: "blocked" });
      } else {
        route.abort("failed");
      }
    });
    await page.route(`http://localhost:3000/api/mobile/chat`, (route) => {
      route.abort("failed");
    });

    await sleep(2000);

    console.log("Sending offline message...");
    await page.fill(inputSelector, "hola desde playwright offline");
    await page.click('button:has-text("Enviar")');
    await sleep(4000);

    const pendingAfterOffline = await page.evaluate(async () => {
      try {
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open("ame-db", 3);
          req.onerror = () => reject(req.error);
          req.onsuccess = () => resolve(req.result);
        });
        const tx = db.transaction("pending_events", "readonly");
        const store = tx.objectStore("pending_events");
        return new Promise((resolve, reject) => {
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || []);
          req.onerror = () => reject(req.error);
        });
      } catch (e) {
        return ["ERROR:" + e.message];
      }
    });
    results.pendingCreated = Array.isArray(pendingAfterOffline) && pendingAfterOffline.length > 0;
    console.log("Pending events after offline:", Array.isArray(pendingAfterOffline) ? pendingAfterOffline.length : pendingAfterOffline);

    if (!results.pendingCreated) {
      results.errors.push("No pending_event created during offline");
    }

    console.log("Restoring backend access...");
    await page.unroute(`http://localhost:8000/**`);
    await page.unroute(`ws://localhost:8000/**`);
    await page.unroute(`http://localhost:3000/api/mobile/chat`);
    await sleep(6000);

    const pendingAfterReconnect = await page.evaluate(async () => {
      try {
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open("ame-db", 3);
          req.onerror = () => reject(req.error);
          req.onsuccess = () => resolve(req.result);
        });
        const tx = db.transaction("pending_events", "readonly");
        const store = tx.objectStore("pending_events");
        return new Promise((resolve, reject) => {
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || []);
          req.onerror = () => reject(req.error);
        });
      } catch (e) {
        return ["ERROR:" + e.message];
      }
    });
    results.pendingCleared = Array.isArray(pendingAfterReconnect) && pendingAfterReconnect.length === 0;
    console.log("Pending events after reconnect:", Array.isArray(pendingAfterReconnect) ? pendingAfterReconnect.length : pendingAfterReconnect);

    if (results.pendingCreated && !results.pendingCleared) {
      results.errors.push("Pending events not cleared after reconnect");
    }

    const chatAfterReconnect = await page.evaluate(async () => {
      try {
        const db = await new Promise((resolve, reject) => {
          const req = indexedDB.open("ame-db", 3);
          req.onerror = () => reject(req.error);
          req.onsuccess = () => resolve(req.result);
        });
        const tx = db.transaction("chat", "readonly");
        const store = tx.objectStore("chat");
        return new Promise((resolve, reject) => {
          const req = store.getAll();
          req.onsuccess = () => resolve(req.result || []);
          req.onerror = () => reject(req.error);
        });
      } catch (e) {
        return ["ERROR:" + e.message];
      }
    });
    const offlineMsgs = Array.isArray(chatAfterReconnect) ? chatAfterReconnect.filter((m) => m.text && m.text.includes("offline")) : [];
    results.noDuplicates = offlineMsgs.length <= 1;
    console.log("Offline messages in history:", offlineMsgs.length);

    if (!results.noDuplicates) {
      results.errors.push("Duplicate offline messages found");
    }
  } catch (err) {
    results.errors.push(String(err));
    console.error("Test error:", err);
  } finally {
    await context.close();
    await browser.close();
  }

  console.log("\n=== PLAYWRIGHT RESULTS ===");
  console.log("IndexedDB stores:", results.stores);
  console.log("Chat history online count:", results.chatHistoryOnline);
  console.log("Offline pending created:", results.pendingCreated);
  console.log("Pending cleared after reconnect:", results.pendingCleared);
  console.log("No duplicates:", results.noDuplicates);
  console.log("Console errors:", results.logs.slice(-10));
  console.log("Errors:", results.errors);

  if (results.errors.length > 0) {
    process.exitCode = 1;
  }
}

main();
