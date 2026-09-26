import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import { auraService } from "./AURAService";

export class CameraGestureService {
  // Capturar foto y enviar a AURA para analisis
  async captureAndAnalyze(): Promise<string> {
    try {
      const photo = await Camera.getPhoto({
        quality: 70,
        allowEditing: false,
        resultType: CameraResultType.Base64,
        source: CameraSource.Camera,
      });

      if (!photo.base64String) throw new Error("Sin imagen");

      auraService.send("AME_PHOTO_ANALYZE", {
        image: photo.base64String,
        mimeType: `image/${photo.format}`,
        ts: Date.now(),
        source: "camera",
      });

      return "Foto enviada a AURA para analisis";
    } catch (err) {
      return `Error al capturar foto: ${err}`;
    }
  }

  // Activar deteccion de gestos via Gesture Bridge
  async startGestureDetection(): Promise<void> {
    auraService.send("GESTURE_BRIDGE_START", {
      source: "AME_APP",
      mode: "continuous",
    });
  }

  stopGestureDetection(): void {
    auraService.send("GESTURE_BRIDGE_STOP", {});
  }

  // Escuchar comandos de gestos detectados
  onGestureCommand(cb: (gesture: string, confidence: number) => void): void {
    auraService.on("GESTURE_DETECTED", (payload: any) => {
      cb(payload.gesture, payload.confidence);
    });
  }

  // Mapear gestos a acciones de AURA
  setupGestureActions(): void {
    this.onGestureCommand((gesture, confidence) => {
      if (confidence < 0.85) return; // ignorar gestos inseguros
      const actions: Record<string, () => void> = {
        thumbs_up: () =>
          auraService.send("AGENT_NEW_TASK", {
            input: "health check rapido",
          }),
        peace: () =>
          auraService.send("GODOT_REMOTE_CMD", {
            command: "TOGGLE_PAUSE",
          }),
        fist: () =>
          auraService.send("NODE_RESTART", {
            node_id: "SSH_TUNNEL",
          }),
        open_palm: () => auraService.send("GET_NODE_LIST", {}),
      };
      actions[gesture]?.();
    });
  }
}

export const cameraGestureService = new CameraGestureService();
