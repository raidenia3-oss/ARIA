// Evolution Metrics for AME
// Fase 39: Métricas de evolución en tiempo real

class EvolutionMetrics {
  constructor() {
    this.metricsDB = null;
  }

  async init() {
    this.metricsDB = await this.openDB("ame-metrics", 1, (db) => {
      if (!db.objectStoreNames.contains("metrics")) {
        db.createObjectStore("metrics", { keyPath: "id" });
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

  async trackEvolution() {
    if (!this.metricsDB) await this.init();

    const metrics = {
      id: `metrics-${Date.now()}`,
      timestamp: Date.now(),
      skillCount: 0,
      averageSuccessRate: 0,
      memoryUsed: performance.memory?.usedJSHeapSize || 0,
      responseTime: 0,
      newSkillsLearned: 0,
      optimizationsApplied: 0,
      resourceSavings: 0,
    };

    await this.addMetric(metrics);
    console.log("📊 Métricas de evolución registradas");
    return metrics;
  }

  async addMetric(metric) {
    return new Promise((resolve, reject) => {
      const tx = this.metricsDB.transaction(["metrics"], "readwrite");
      const store = tx.objectStore("metrics");
      const req = store.add(metric);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async getLatestMetrics() {
    return new Promise((resolve, reject) => {
      const tx = this.metricsDB.transaction(["metrics"], "readonly");
      const store = tx.objectStore("metrics");
      const req = store.getAll();
      req.onsuccess = () => {
        const all = req.result || [];
        const latest = all[all.length - 1];
        resolve(latest);
      };
      req.onerror = () => reject(req.error);
    });
  }
}

export const evolutionMetrics = new EvolutionMetrics();
