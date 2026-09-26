import { LocalNotifications } from "@capacitor/local-notifications";
import { auraService } from "./AURAService";

export type NotifPriority = "low" | "normal" | "high" | "critical";

export interface SmartNotif {
  id: number;
  title: string;
  body: string;
  priority: NotifPriority;
  action?: string;
  data?: any;
}

export class NotificationService {
  private rules: Map<string, NotifPriority> = new Map([
    ["NODE_OFFLINE", "high"],
    ["SSH_TUNNEL_DOWN", "high"],
    ["VULN_FOUND", "critical"],
    ["TASK_COMPLETE", "low"],
    ["AME_UPDATED", "normal"],
    ["AURA_DISCONNECTED", "critical"],
    ["LEVEL_UP", "normal"],
  ]);

  // Inicializar permisos y escuchar eventos de AURA
  async init(): Promise<void> {
    try {
      await LocalNotifications.requestPermissions();
    } catch {
      console.warn("LocalNotifications no disponible");
    }

    auraService.on("any", async (msg: any) => {
      const priority = this.rules.get(msg.event);
      if (priority) {
        await this.send({
          id: Date.now(),
          title: this.getTitle(msg.event),
          body: this.getBody(msg.event, msg.payload),
          priority,
          action: msg.event,
          data: msg.payload,
        });
      }
    });

    // Alertas criticas inmediatas
    auraService.on("CRITICAL_ALERT", async (payload: any) => {
      await this.send({
        id: Date.now(),
        title: "AURA - Alerta critica",
        body: payload.message || "Requiere atencion inmediata",
        priority: "critical",
        data: payload,
      });
      if (navigator.vibrate) navigator.vibrate([300, 100, 300, 100, 300]);
    });
  }

  // Enviar notificacion local
  async send(notif: SmartNotif): Promise<void> {
    // No molestar con notificaciones de baja prioridad muy seguidas
    if (notif.priority === "low") {
      const lastLow = parseInt(localStorage.getItem("last_low_notif") || "0");
      if (Date.now() - lastLow < 60000) return;
      localStorage.setItem("last_low_notif", String(Date.now()));
    }

    try {
      await LocalNotifications.schedule({
        notifications: [
          {
            id: notif.id,
            title: notif.title,
            body: notif.body,
            schedule: { at: new Date(Date.now() + 100) },
            extra: notif.data,
            actionTypeId: notif.action || "",
          },
        ],
      });
    } catch {
      console.warn("Error enviando notificacion");
    }
  }

  // Notificacion bidireccional — tambien avisa a la PC
  async sendToAURA(title: string, body: string): Promise<void> {
    auraService.send("AME_NOTIFICATION", { title, body, ts: Date.now() });
    await this.send({ id: Date.now(), title, body, priority: "normal" });
  }

  private getTitle(event: string): string {
    const titles: Record<string, string> = {
      NODE_OFFLINE: "Nodo offline",
      SSH_TUNNEL_DOWN: "SSH Tunnel caido",
      VULN_FOUND: "Vulnerabilidad detectada",
      TASK_COMPLETE: "Tarea completada",
      AME_UPDATED: "AME actualizado",
      AURA_DISCONNECTED: "AURA desconectado",
      LEVEL_UP: "Subiste de nivel",
    };
    return titles[event] || "AURA/AME";
  }

  private getBody(event: string, payload: any): string {
    switch (event) {
      case "NODE_OFFLINE":
        return `El nodo ${payload?.node_id || "desconocido"} se desconecto`;
      case "TASK_COMPLETE":
        return payload?.task || "Tarea ejecutada correctamente";
      case "LEVEL_UP":
        return `Nivel ${payload?.level || "?"} alcanzado`;
      default:
        return JSON.stringify(payload || {}).slice(0, 100);
    }
  }
}

export const notificationService = new NotificationService();
