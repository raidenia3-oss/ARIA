class AURAService {
  private ws: WebSocket | null = null;
  private config: AURAConfig;
  private reconnectTimer: any;
  private listeners: Map<string, Function[]> = new Map();

  async loadConfig(): Promise<AURAConfig> {
    try {
      const { Filesystem, Directory } = await import("@capacitor/filesystem");
      const result = await Filesystem.readFile({
        path: "ame_config.json",
        directory: Directory.ExternalStorage,
        encoding: "utf8" as any,
      });
      this.config = JSON.parse(result.data as string);
      console.log("✅ Config cargada:", this.config.eventbus_url);
    } catch {
      this.config = {
        eventbus_url: "ws://192.168.1.100:8765",
        godot_url: "ws://192.168.1.100:9090",
        node_id: "AME_ANDROID_01",
        sync_interval: 5000,
      };
      console.log("⚠️ Usando config por defecto (WiFi local)");
    }
    return this.config;
  }

  async connect(): Promise<void> {
    await this.loadConfig();
    this.ws = new WebSocket(this.config.eventbus_url);

    this.ws.onopen = () => {
      console.log("🟢 AURA conectado");
      this.emit("connection", { status: "connected" });
      this.send("AME_REGISTER", {
        node_id: this.config.node_id,
        capabilities: [
          "telemetry",
          "camera",
          "gps",
          "filesystem",
          "notifications",
        ],
      });
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.emit(msg.event, msg.payload);
      this.emit("any", msg);
    };

    this.ws.onclose = () => {
      console.log("🔴 AURA desconectado, reconectando en 5s...");
      this.emit("connection", { status: "disconnected" });
      this.reconnectTimer = setTimeout(() => this.connect(), 5000);
    };

    this.ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };
  }

  send(event: string, payload: any = {}): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          node: "AME_ANDROID",
          event,
          payload,
          ts: Date.now(),
        }),
      );
    }
  }

  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  private emit(event: string, data: any): void {
    this.listeners.get(event)?.forEach((cb) => cb(data));
  }

  disconnect(): void {
    clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export const auraService = new AURAService();
export interface AURAConfig {
  eventbus_url: string;
  godot_url: string;
  node_id: string;
  sync_interval: number;
}
