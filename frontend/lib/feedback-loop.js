// Feedback Loop for AME
// Fase 40: Feedback loop automático

class FeedbackLoop {
  constructor() {
    this.db = null;
  }

  async init() {
    this.db = await this.openDB("ame-feedback", 1, (db) => {
      if (!db.objectStoreNames.contains("patterns")) {
        db.createObjectStore("patterns", { keyPath: "action" });
      }
    });
  }

  openDB(name, version, onUpgrade) {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(name, version);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      if (onUpgrade) request.onupgradeneeded = onUpgrade;
    });
  }

  async startPassiveEvaluation() {
    if (!this.db) await this.init();
    console.log("🔄 Iniciando feedback loop pasivo...");

    window.addEventListener("ame:interaction", async (event) => {
      const { action, result, timeSpent, userSatisfaction } = event.detail;
      await this.logInteraction(action, result, timeSpent, userSatisfaction);
      if (userSatisfaction < 3) {
        await this.improveAction(action);
      }
    });
  }

  async logInteraction(action, result, timeSpent, userSatisfaction) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction(["patterns"], "readwrite");
      const store = tx.objectStore("patterns");
      const record = {
        action,
        result,
        timeSpent,
        userSatisfaction,
        timestamp: Date.now(),
      };
      const req = store.put(record);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }

  async improveAction(action) {
    console.log(`🔧 Mejorando acción: ${action}`);
  }
}

export const feedbackLoop = new FeedbackLoop();
