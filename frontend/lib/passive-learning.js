// Passive Learning System for AME
// Fase 36: Autoaprendizaje pasivo

class PassiveLearning {
  constructor() {
    this.learningDB = null;
    this.patterns = {};
    this.skills = {};
  }

  async init() {
    // Inicializar IndexedDB para aprendizaje
    this.learningDB = await this.openIndexedDB("ame-learning", {
      interactions: "id, timestamp, userId, action, result",
      patterns: "patternId, frequency, effectiveness",
      skills: "skillId, level, success_rate",
      optimizations: "optimizationId, result, resource_saved",
    });
  }

  async openIndexedDB(name, stores) {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(name, 1);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        for (const [storeName, indexes] of Object.entries(stores)) {
          if (!db.objectStoreNames.contains(storeName)) {
            const store = db.createObjectStore(storeName, { keyPath: "id" });
            const indexList = indexes.split(",").map((i) => i.trim());
            indexList.forEach((index) => {
              if (index !== "id") store.createIndex(index, index);
            });
          }
        }
      };
    });
  }

  // Registrar cada interacción
  async logInteraction(userId, action, result, resourceUsed) {
    if (!this.learningDB) await this.init();

    const interaction = {
      id: `${userId}-${Date.now()}`,
      timestamp: Date.now(),
      userId,
      action,
      result,
      resourceUsed,
      success: result === "success",
    };

    await this.addToDB("interactions", interaction);

    // Trigger análisis automático
    await this.analyzePatterns();
  }

  async addToDB(storeName, data) {
    return new Promise((resolve, reject) => {
      const transaction = this.learningDB.transaction([storeName], "readwrite");
      const store = transaction.objectStore(storeName);
      const request = store.add(data);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async getAllFromDB(storeName) {
    return new Promise((resolve, reject) => {
      const transaction = this.learningDB.transaction([storeName], "readonly");
      const store = transaction.objectStore(storeName);
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Analizar patrones de comportamiento
  async analyzePatterns() {
    if (!this.learningDB) await this.init();

    console.log("🧠 Analizando patrones...");

    const interactions = await this.getAllFromDB("interactions");

    // Agrupar por acción
    const actionGroups = this.groupBy(interactions, "action");

    for (const [action, items] of Object.entries(actionGroups)) {
      const successRate = items.filter((i) => i.success).length / items.length;
      const avgResource =
        items.reduce((sum, i) => sum + (i.resourceUsed || 0), 0) / items.length;

      this.patterns[action] = {
        frequency: items.length,
        successRate,
        avgResource,
        lastUpdated: Date.now(),
      };

      // Si success rate es bajo, aprende a mejorar
      if (successRate < 0.8) {
        await this.improveAction(action);
      }
    }

    console.log(
      `✅ ${Object.keys(this.patterns).length} patrones identificados`,
    );
  }

  // Mejorar acciones fallidas
  async improveAction(action) {
    console.log(`🔄 Mejorando acción: ${action}`);

    const pattern = this.patterns[action];

    // Estrategias de mejora
    const improvements = [
      { type: "retry_strategy", effect: 0.15 },
      { type: "fallback_path", effect: 0.2 },
      { type: "cache_result", effect: 0.1 },
      { type: "parallel_execution", effect: 0.12 },
    ];

    for (const improvement of improvements) {
      const newRate = await this.testImprovement(action, improvement);
      if (newRate > pattern.successRate) {
        pattern.improvement = improvement;
        pattern.successRate = newRate;
        console.log(
          `   ✅ ${improvement.type} mejoró success rate a ${newRate}`,
        );
      }
    }
  }

  async testImprovement(action, improvement) {
    // Simular mejora
    return this.patterns[action].successRate + improvement.effect;
  }

  groupBy(arr, key) {
    return arr.reduce((result, item) => {
      (result[item[key]] = result[item[key]] || []).push(item);
      return result;
    }, {});
  }
}

// Exportar instancia singleton
export const passiveLearning = new PassiveLearning();
