"use client";

import { SyncEvent } from "./ame-events";

interface AMEData {
  id: string;
  name: string;
  status: string;
  lastSync?: string;
  offline?: boolean;
}

interface DeviceConfigEntry {
  key: string;
  value: unknown;
}

export interface PendingEvent {
  eventId: string;
  createdAt: string;
  type: string;
  payload: Record<string, unknown>;
}

interface NewsArticle {
  url: string;
  title: string;
  content: string;
  timestamp: string;
}

class LocalDB {
  private db: IDBDatabase | null = null;
  private static instance: LocalDB;

  static getInstance(): LocalDB {
    if (!LocalDB.instance) {
      LocalDB.instance = new LocalDB();
    }
    return LocalDB.instance;
  }

  async init(): Promise<void> {
    if (this.db) return;
    return new Promise((resolve, reject) => {
      const request = indexedDB.open("ame-db", 3);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (e: IDBVersionChangeEvent) => {
        const db = (e.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains("ames")) {
          db.createObjectStore("ames", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("news")) {
          db.createObjectStore("news", { keyPath: "url" });
        }
        if (!db.objectStoreNames.contains("sync")) {
          db.createObjectStore("sync", { keyPath: "timestamp" });
        }
        if (!db.objectStoreNames.contains("chat")) {
          db.createObjectStore("chat", { keyPath: "id", autoIncrement: true });
        }
        if (!db.objectStoreNames.contains("events")) {
          db.createObjectStore("events", { keyPath: "eventId" });
        }
        if (!db.objectStoreNames.contains("device_config")) {
          db.createObjectStore("device_config", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("pending_events")) {
          const pendingStore = db.createObjectStore("pending_events", { keyPath: "eventId" });
          pendingStore.createIndex("by_createdAt", "createdAt", { unique: false });
        }
      };
    });
  }

  private async ensureInit(): Promise<void> {
    if (!this.db) await this.init();
  }

  async saveAME(ame: AMEData): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("ames", "readwrite");
    tx.objectStore("ames").put({ ...ame, lastSync: new Date().toISOString() });
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getAME(id: string): Promise<AMEData | undefined> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("ames", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("ames").get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = reject;
    });
  }

  async getAllAMEs(): Promise<AMEData[]> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("ames", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("ames").getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = reject;
    });
  }

  async saveNews(article: NewsArticle): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("news", "readwrite");
    tx.objectStore("news").put(article);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getAllNews(): Promise<NewsArticle[]> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("news", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("news").getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = reject;
    });
  }

  async saveChatMessage(msg: {
    role: string;
    text: string;
    ameId: string;
  }): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("chat", "readwrite");
    tx.objectStore("chat").put({
      ...msg,
      timestamp: new Date().toISOString(),
    });
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getChatHistory(ameId: string): Promise<Array<{ role: string; text: string; ameId: string; timestamp: string }>> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("chat", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("chat").getAll();
      request.onsuccess = () => {
        const all = request.result || [];
        resolve(
          all.filter(
            (m: { role: string; text: string; ameId: string; timestamp: string }) =>
              m.ameId === ameId,
          ),
        );
      };
      request.onerror = reject;
    });
  }

  async saveEvent(event: SyncEvent): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("events", "readwrite");
    tx.objectStore("events").put(event as unknown as IDBValidKey);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getEvent(eventId: string): Promise<SyncEvent | undefined> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("events", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("events").get(eventId);
      request.onsuccess = () => resolve(request.result as SyncEvent);
      request.onerror = reject;
    });
  }

  async getAllEvents(): Promise<SyncEvent[]> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("events", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("events").getAll();
      request.onsuccess = () => resolve((request.result || []) as SyncEvent[]);
      request.onerror = reject;
    });
  }

  async clearEvents(): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("events", "readwrite");
    tx.objectStore("events").clear();
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async saveConfig(key: string, value: unknown): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("device_config", "readwrite");
    tx.objectStore("device_config").put({ key, value } as unknown as IDBValidKey);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getConfig<T = unknown>(key: string, defaultValue?: T): Promise<T | undefined> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("device_config", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("device_config").get(key);
      request.onsuccess = () => {
        const entry = request.result as DeviceConfigEntry | undefined;
        resolve((entry?.value as T) ?? defaultValue);
      };
      request.onerror = reject;
    });
  }

  async savePendingEvent(event: PendingEvent): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("pending_events", "readwrite");
    tx.objectStore("pending_events").put(event as unknown as IDBValidKey);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async getPendingEvents(): Promise<PendingEvent[]> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("pending_events", "readonly");
    return new Promise((resolve, reject) => {
      const request = tx.objectStore("pending_events").getAll();
      request.onsuccess = () => resolve((request.result || []) as PendingEvent[]);
      request.onerror = reject;
    });
  }

  async getPendingEventsByCreatedAt(): Promise<PendingEvent[]> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("pending_events", "readonly");
    const store = tx.objectStore("pending_events");
    const index = store.index("by_createdAt");
    return new Promise((resolve, reject) => {
      const request = index.getAll();
      request.onsuccess = () => resolve((request.result || []) as PendingEvent[]);
      request.onerror = reject;
    });
  }

  async deletePendingEvent(eventId: string): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("pending_events", "readwrite");
    tx.objectStore("pending_events").delete(eventId);
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async clearPendingEvents(): Promise<void> {
    await this.ensureInit();
    const tx = (this.db as IDBDatabase).transaction("pending_events", "readwrite");
    tx.objectStore("pending_events").clear();
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = reject;
    });
  }

  async setLastSync(timestamp: string): Promise<void> {
    await this.saveConfig("lastSync", timestamp);
  }

  async getLastSync(): Promise<string | null> {
    const result = await this.getConfig<string>("lastSync");
    return result ?? null;
  }

  async hasPendingEvents(): Promise<boolean> {
    const events = await this.getPendingEvents();
    return events.length > 0;
  }
}

export default LocalDB;
