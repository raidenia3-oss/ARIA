// ═══════════════════════════════════════════════════════════════
// QRScannerService.ts — Lector de QR integrado para AME
// Fallback a @capacitor/camera si mlkit no está disponible
// ═══════════════════════════════════════════════════════════════

import { ameChatService } from "./AMEChatService";

export class QRScannerService {
  private scannerAvailable = false;

  constructor() {
    this.checkScanner();
  }

  private async checkScanner(): Promise<void> {
    try {
      // Intentar cargar @capacitor-mlkit/barcode-scanning
      const mod = await import("@capacitor-mlkit/barcode-scanning");
      this.scannerAvailable = true;
      this.logger("Scanner mlkit disponible");
    } catch {
      this.logger("mlkit no disponible, usando cámara como fallback");
      this.scannerAvailable = false;
    }
  }

  async scan(): Promise<string | null> {
    if (this.scannerAvailable) {
      return this.scanWithMlkit();
    }
    return this.scanWithCamera();
  }

  private async scanWithMlkit(): Promise<string | null> {
    try {
      const { BarcodeScanner } =
        await import("@capacitor-mlkit/barcode-scanning");

      const { camera } = await BarcodeScanner.checkPermissions();
      if (camera !== "granted") {
        await BarcodeScanner.requestPermissions();
      }

      const result = await BarcodeScanner.scan();
      if (result.barcodes.length > 0) {
        const qrData = result.barcodes[0].rawValue || "";
        await this.processQR(qrData);
        return qrData;
      }
      return null;
    } catch (err) {
      this.logger("Error escaneando QR con mlkit: " + err);
      return null;
    }
  }

  // Fallback: usar cámara nativa para capturar imagen
  private async scanWithCamera(): Promise<string | null> {
    try {
      const { Camera, CameraResultType, CameraSource } =
        await import("@capacitor/camera");

      const image = await Camera.getPhoto({
        quality: 80,
        allowEditing: false,
        resultType: CameraResultType.Base64,
        source: CameraSource.Camera,
      });

      this.logger("Imagen capturada, procesando QR...");
      ameChatService.receiveMessage(
        "📷 Imagen capturada desde cámara. " +
          "Para escanear QR instala @capacitor-mlkit/barcode-scanning.",
        "system",
        "camera",
      );
      return null;
    } catch (err) {
      this.logger("Error con cámara: " + err);
      return null;
    }
  }

  async processQR(data: string): Promise<void> {
    this.logger("QR escaneado: " + data);
    const type = this.detectQRType(data);

    const message =
      "📷 QR escaneado:\n```\n" +
      data +
      "```\n" +
      "Tipo detectado: " +
      type +
      "\n¿Qué quieres hacer con esto?";
    ameChatService.receiveMessage(message, "system", "qr_scanner");

    if (type === "aura_config") {
      await this.processAURAConfig(data);
    }
    if (type === "wifi") {
      await this.processWiFiQR(data);
    }
  }

  detectQRType(data: string): string {
    if (data.startsWith("aura://")) return "aura_config";
    if (data.startsWith("WIFI:")) return "wifi";
    if (data.startsWith("http")) return "url";
    if (data.startsWith("BEGIN:VCARD")) return "contact";
    if (/^\d+$/.test(data)) return "number";
    try {
      JSON.parse(data);
      return "json";
    } catch {
      /* */
    }
    return "text";
  }

  private async processAURAConfig(data: string): Promise<void> {
    try {
      const url = new URL(data);
      const ip = url.hostname;
      const port = url.port || "8765";
      const apiKey = url.searchParams.get("key") || "";

      ameChatService.receiveMessage(
        "Configuración AURA detectada:\nIP: " +
          ip +
          "\nPuerto: " +
          port +
          "\n¿Conectar ahora?",
        "system",
        "qr_scanner",
      );

      // Guardar configuración para conectar
      const config = {
        eventbus_url: "ws://" + ip + ":" + port,
        node_id: "AME_ANDROID_01",
        sync_interval: 5000,
      };
      localStorage.setItem("ame_config", JSON.stringify(config));

      ameChatService.receiveMessage(
        "Conectado a AURA Core en " + ip + ":" + port,
        "system",
        "qr_scanner",
      );
    } catch (err) {
      this.logger("Error procesando QR de AURA: " + err);
    }
  }

  private async processWiFiQR(data: string): Promise<void> {
    const ssid = data.match(/S:([^;]+)/)?.[1] || "";
    const pass = data.match(/P:([^;]+)/)?.[1] || "";

    ameChatService.receiveMessage(
      "Red WiFi detectada:\nSSID: " + ssid + "\nContraseña: " + pass,
      "system",
      "qr_scanner",
    );

    localStorage.setItem("wifi_ssid", ssid);
    localStorage.setItem("wifi_pass", pass);
  }

  // Generar QR de configuración AURA
  generateAURAQR(ip: string, port = "8765", apiKey = ""): string {
    return "aura://" + ip + ":" + port + "?key=" + apiKey;
  }

  private logger(msg: string): void {
    console.log("[QRScanner] " + msg);
  }
}

export const qrScannerService = new QRScannerService();
