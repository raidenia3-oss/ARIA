const events = new Map<string, { url: string; events: string[]; createdAt: number }>();

const WebhookManager = {
  register(id: string, url: string, eventsList: string[]) {
    events.set(id, { url, events: eventsList, createdAt: Date.now() });
    return { success: true, id };
  },

  unregister(id: string) {
    events.delete(id);
    return { success: true };
  },

  get(id: string) {
    return events.get(id) || null;
  },

  getAll() {
    return Array.from(events.entries()).map(([id, data]) => ({ id, ...data }));
  },

  async trigger(eventType: string, payload: unknown) {
    const targets = Array.from(events.values()).filter((e) => e.events.includes(eventType));

    return Promise.all(
      targets.map(async (target) => {
        try {
          const response = await fetch(target.url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event: eventType, data: payload, timestamp: Date.now() }),
          });
          return { url: target.url, status: response.status };
        } catch (error) {
          return { url: target.url, error: (error as Error).message };
        }
      }),
    );
  },
};

export { WebhookManager };
