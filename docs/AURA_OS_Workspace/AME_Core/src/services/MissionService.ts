import { auraService } from "./AURAService";

export interface Mission {
  id: string;
  title: string;
  description: string;
  type: "audit" | "maintenance" | "game" | "update";
  status: "pending" | "running" | "complete" | "failed";
  progress: number;
  reward?: { xp: number; gold: number; buff?: string };
  createdAt: number;
  completedAt?: number;
  steps: string[];
  currentStep: number;
}

export class MissionService {
  private missions: Mission[] = [];
  private listeners: ((m: Mission[]) => void)[] = [];

  constructor() {
    auraService.on("MISSION_UPDATE", (payload: any) => {
      this.updateMission(payload);
    });
    auraService.on("MISSION_COMPLETE", (payload: any) => {
      this.completeMission(payload);
    });
    auraService.on("TASK_COMPLETE", (payload: any) => {
      // Convertir tareas de AURA en misiones completadas
      this.addMission({
        id: `m_${Date.now()}`,
        title: "Tarea completada",
        description: payload.task || "",
        type: "maintenance",
        status: "complete",
        progress: 100,
        createdAt: Date.now(),
        completedAt: Date.now(),
        steps: [],
        currentStep: 0,
      });
    });
    auraService.on("connection", () => {
      auraService.send("GET_MISSIONS", {});
    });
  }

  // Crear nueva mision
  createMission(data: Partial<Mission>): Mission {
    const mission: Mission = {
      id: `m_${Date.now()}`,
      title: data.title || "Nueva mision",
      description: data.description || "",
      type: data.type || "maintenance",
      status: "pending",
      progress: 0,
      reward: data.reward,
      createdAt: Date.now(),
      steps: data.steps || [],
      currentStep: 0,
    };
    this.missions.unshift(mission);
    auraService.send("CREATE_MISSION", mission);
    this.notify();
    return mission;
  }

  // Misiones predefinidas frecuentes
  createHealthCheckMission(): Mission {
    return this.createMission({
      title: "Health Check completo",
      description: "Verificar estado de todos los nodos",
      type: "maintenance",
      steps: [
        "Verificar EventBus",
        "Verificar SSH",
        "Verificar Godot",
        "Generar reporte",
      ],
      reward: { xp: 50, gold: 10 },
    });
  }

  createUpdateMission(): Mission {
    return this.createMission({
      title: "Actualizar AME",
      description: "Deploy OTA de la app AME",
      type: "update",
      steps: ["Build web", "Sync Capacitor", "Deploy OTA", "Notificar celular"],
      reward: { xp: 100, gold: 25, buff: "XP_BOOST" },
    });
  }

  createAuditMission(target: string): Mission {
    return this.createMission({
      title: `Auditoria: ${target}`,
      description: `Escaneo completo de ${target}`,
      type: "audit",
      steps: ["Port scan", "Vuln scan", "Hash extract", "Reporte"],
      reward: { xp: 200, gold: 50, buff: "SCAN_SPEED" },
    });
  }

  getMissions(): Mission[] {
    return this.missions;
  }
  getPending(): Mission[] {
    return this.missions.filter((m) => m.status === "pending");
  }
  getCompleted(): Mission[] {
    return this.missions.filter((m) => m.status === "complete");
  }
  getRunning(): Mission[] {
    return this.missions.filter((m) => m.status === "running");
  }

  onChange(cb: (m: Mission[]) => void): void {
    this.listeners.push(cb);
    cb(this.missions);
  }

  private addMission(m: Mission): void {
    this.missions.unshift(m);
    if (this.missions.length > 50) this.missions = this.missions.slice(0, 50);
    this.notify();
  }

  private updateMission(payload: any): void {
    const m = this.missions.find((m) => m.id === payload.id);
    if (m) {
      Object.assign(m, payload);
      this.notify();
    }
  }

  private completeMission(payload: any): void {
    const m = this.missions.find((m) => m.id === payload.id);
    if (m) {
      m.status = "complete";
      m.progress = 100;
      m.completedAt = Date.now();
      this.notify();
    }
  }

  private notify(): void {
    this.listeners.forEach((cb) => cb(this.missions));
  }
}

export const missionService = new MissionService();
