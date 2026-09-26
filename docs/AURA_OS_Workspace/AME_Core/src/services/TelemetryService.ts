import { auraService } from "./AURAService";

class TelemetryService {
  private interval: any;

  async startStreaming(intervalMs = 5000): Promise<void> {
    this.interval = setInterval(async () => {
      const data = await this.collectAll();
      auraService.send("AME_TELEMETRY", data);
    }, intervalMs);
    console.log("📡 Telemetría iniciada");
  }

  async collectAll() {
    const [battery, position, deviceInfo] = await Promise.allSettled([
      this.getBattery(),
      this.getGPS(),
      this.getDeviceInfo(),
    ]);

    return {
      battery: battery.status === "fulfilled" ? battery.value : null,
      gps: position.status === "fulfilled" ? position.value : null,
      device: deviceInfo.status === "fulfilled" ? deviceInfo.value : null,
      memory: (performance as any).memory?.usedJSHeapSize || null,
      timestamp: Date.now(),
      node_id: "AME_ANDROID_01",
    };
  }

  async getBattery() {
    const nav = navigator as any;
    if (nav.getBattery) {
      const bat = await nav.getBattery();
      return {
        level: Math.round(bat.level * 100),
        charging: bat.charging,
      };
    }
    return null;
  }

  async getGPS() {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
          }),
        (err) => reject(err),
        { timeout: 5000, maximumAge: 30000 },
      );
    });
  }

  async getDeviceInfo() {
    const { Device } = await import("@capacitor/device");
    const info = await Device.getInfo();
    const battery = await Device.getBatteryInfo();
    return { ...info, ...battery };
  }

  stop(): void {
    clearInterval(this.interval);
  }
}

export const telemetryService = new TelemetryService();
