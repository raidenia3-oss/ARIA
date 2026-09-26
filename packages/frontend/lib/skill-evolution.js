// Skill Evolution for AME
// Fase 37: Nuevas habilidades automáticas

class SkillEvolution {
  constructor() {
    this.skillsDB = null;
  }

  async init() {
    this.skillsDB = await this.openDB("ame-skills", 1, (db) => {
      if (!db.objectStoreNames.contains("skills")) {
        db.createObjectStore("skills", { keyPath: "id" });
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

  async discoverNewSkills() {
    if (!this.skillsDB) await this.init();
    console.log("🌟 Descubriendo nuevas habilidades...");

    const newSkills = [
      { name: "Predicción de necesidades", id: "predict_needs" },
      { name: "Optimización de caché", id: "optimize_cache" },
      { name: "Compresión de datos", id: "compress_data" },
    ];

    for (const skill of newSkills) {
      const exists = await this.getSkill(skill.id);
      if (!exists) {
        await this.learnSkill(skill);
      }
    }
  }

  async learnSkill(skill) {
    console.log(`📚 Aprendiendo: ${skill.name}`);
    const record = {
      id: skill.id,
      name: skill.name,
      level: 1,
      success_rate: 0,
      resource_cost: 0,
      learnedAt: Date.now(),
    };
    await this.addSkill(record);
    console.log(`✅ Skill aprendido: ${skill.name}`);
  }

  async addSkill(skill) {
    return new Promise((resolve, reject) => {
      const tx = this.skillsDB.transaction(["skills"], "readwrite");
      const store = tx.objectStore("skills");
      const req = store.add(skill);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async getSkill(id) {
    return new Promise((resolve, reject) => {
      const tx = this.skillsDB.transaction(["skills"], "readonly");
      const store = tx.objectStore("skills");
      const req = store.get(id);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async getAllSkills() {
    return new Promise((resolve, reject) => {
      const tx = this.skillsDB.transaction(["skills"], "readonly");
      const store = tx.objectStore("skills");
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  shouldLearnSkill(skill) {
    const trigger = skill.trigger && skill.trigger.length;
    return trigger && trigger > 5;
  }
}

export const skillEvolution = new SkillEvolution();
