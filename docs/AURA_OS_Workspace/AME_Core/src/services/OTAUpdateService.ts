class OTAUpdateService {
  private currentVersion = "1.0.0";
  private updateUrl: string;

  constructor() {
    this.updateUrl = "https://TU_USUARIO.github.io/aura-ame";
  }

  async checkForUpdates(): Promise<boolean> {
    try {
      const response = await fetch(
        `${this.updateUrl}/version.json?t=${Date.now()}`,
      );
      const remote = await response.json();

      if (remote.version !== this.currentVersion) {
        console.log(`🔄 Update disponible: ${remote.version}`);
        await this.applyUpdate(remote);
        return true;
      }
      return false;
    } catch (err) {
      console.log("Sin conexión o sin updates:", err);
      return false;
    }
  }

  async applyUpdate(updateInfo: any): Promise<void> {
    const { Filesystem, Directory } = await import("@capacitor/filesystem");

    await Filesystem.writeFile({
      path: "pending_update.json",
      data: JSON.stringify(updateInfo),
      directory: Directory.Data,
      encoding: "utf8" as any,
    });

    const { auraService } = await import("./AURAService");
    auraService.send("AME_UPDATED", {
      old_version: this.currentVersion,
      new_version: updateInfo.version,
    });

    console.log(`✅ Update aplicado: ${updateInfo.version}`);
    console.log("🔄 Reiniciando app...");
    setTimeout(() => window.location.reload(), 2000);
  }

  startAutoCheck(intervalMinutes = 30): void {
    setInterval(() => this.checkForUpdates(), intervalMinutes * 60 * 1000);
    const { auraService } = require("./AURAService");
    auraService.on("connection", () => this.checkForUpdates());
    console.log(`⏰ Auto-update cada ${intervalMinutes} minutos`);
  }
}

export const otaService = new OTAUpdateService();
