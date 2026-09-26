"use client";

class SyncEngine {
  private static instance: SyncEngine;
  private isOnline: boolean = true;
  private queue: Array<{ url: string; data: unknown }> = [];

  static getInstance(): SyncEngine {
    if (!SyncEngine.instance) {
      SyncEngine.instance = new SyncEngine();
    }
    return SyncEngine.instance;
  }

  init(): void {
    this.isOnline = navigator.onLine;
    this.restoreQueue();

    window.addEventListener("online", () => {
      this.isOnline = true;
      this.syncQueue();
    });

    window.addEventListener("offline", () => {
      this.isOnline = false;
    });
  }

  private restoreQueue(): void {
    try {
      const saved = localStorage.getItem("syncQueue");
      if (saved) {
        this.queue = JSON.parse(saved);
      }
    } catch {}
  }

  private saveQueue(): void {
    try {
      localStorage.setItem("syncQueue", JSON.stringify(this.queue));
    } catch {}
  }

  async syncQueue(): Promise<void> {
    if (!this.isOnline || this.queue.length === 0) return;

    const pending = [...this.queue];
    this.queue = [];
    this.saveQueue();

    for (const item of pending) {
      try {
        const res = await fetch(item.url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item.data),
        });
        if (!res.ok) {
          this.queue.push(item);
        }
      } catch {
        this.queue.push(item);
      }
    }
    this.saveQueue();
  }

  async addToQueue(url: string, data: unknown): Promise<void> {
    this.queue.push({ url, data });
    this.saveQueue();
    if (this.isOnline) {
      await this.syncQueue();
    }
  }

  getQueueLength(): number {
    return this.queue.length;
  }

  isOnlineStatus(): boolean {
    return this.isOnline;
  }
}

export default SyncEngine;
