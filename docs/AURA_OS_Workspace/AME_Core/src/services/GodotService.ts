import { auraService } from "./AURAService";

class GodotService {
  private ws: WebSocket | null = null;
  private godotUrl = "ws://localhost:9090";

  async connect(url?: string): Promise<void> {
    const config = await auraService.loadConfig();
    this.godotUrl = url || config.godot_url;

    this.ws = new WebSocket(this.godotUrl);

    this.ws.onopen = () => {
      console.log("🎮 Godot conectado desde AME");
      this.sendHeroUpdate();
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.handleGodotEvent(msg);
    };

    this.ws.onclose = () => {
      setTimeout(() => this.connect(), 10000);
    };
  }

  async sendHeroUpdate(): Promise<void> {
    const telemetry = await import("./TelemetryService").then((m) =>
      m.telemetryService.collectAll(),
    );

    this.send("HERO_UPDATE", {
      defense_modifier: (telemetry.battery?.level || 100) / 100,
      exploration_bonus: telemetry.gps ? 1.2 : 1.0,
      device_name: telemetry.device?.model || "Unknown",
    });
  }

  handleGodotEvent(msg: any): void {
    switch (msg.event) {
      case "TRIGGER_NOTIFICATION":
        this.triggerNotification(msg.payload);
        break;
      case "REQUEST_CAMERA":
        this.activateCamera();
        break;
      case "PLAY_VICTORY":
        if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
        break;
      case "REQUEST_TELEMETRY":
        this.sendHeroUpdate();
        break;
    }
  }

  async triggerNotification(data: any): Promise<void> {
    const { LocalNotifications } =
      await import("@capacitor/local-notifications");
    await LocalNotifications.schedule({
      notifications: [
        {
          id: Date.now(),
          title: data.title || "⚔️ AURA/AME",
          body: data.body || "Evento en el juego",
          schedule: { at: new Date(Date.now() + 100) },
        },
      ],
    });
  }

  async activateCamera(): Promise<void> {
    const { Camera, CameraResultType } = await import("@capacitor/camera");
    const photo = await Camera.getPhoto({
      quality: 50,
      resultType: CameraResultType.Base64,
    });
    auraService.send("AME_PHOTO", { data: photo.base64String });
  }

  send(event: string, payload: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event, payload, source: "AME" }));
    }
  }
}

export const godotService = new GodotService();
