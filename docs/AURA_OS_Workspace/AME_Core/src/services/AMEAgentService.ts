import { auraService } from "./AURAService";
import { voiceService } from "./VoiceService";

export interface AgentTask {
  id: string;
  input: string;
  status: "pending" | "running" | "done" | "error";
  steps: AgentStep[];
  result?: string;
  createdAt: number;
}

export interface AgentStep {
  tool: string;
  args: Record<string, any>;
  result?: string;
  status: "pending" | "ok" | "error";
}

export class AMEAgentService {
  private tasks: AgentTask[] = [];
  private listeners: ((tasks: AgentTask[]) => void)[] = [];
  private apiKey: string = "";

  constructor() {
    // Recibir resultados del agente Python en Termux
    auraService.on("AGENT_TASK_UPDATE", (payload: any) => {
      this.updateTask(payload);
    });
    auraService.on("AGENT_TASK_COMPLETE", (payload: any) => {
      this.completeTask(payload);
    });
    auraService.on("AGENT_STEP", (payload: any) => {
      this.addStep(payload);
    });
    // Cargar API key guardada
    this.apiKey = localStorage.getItem("gemini_api_key") || "";
  }

  // Enviar tarea al agente en Termux
  async sendTask(input: string): Promise<AgentTask> {
    const task: AgentTask = {
      id: `task_${Date.now()}`,
      input,
      status: "pending",
      steps: [],
      createdAt: Date.now(),
    };
    this.tasks.unshift(task);
    this.notify();

    auraService.send("AGENT_NEW_TASK", {
      task_id: task.id,
      input,
      api_key: this.apiKey,
      context: { platform: "AME_APP", source: "mobile_ui" },
    });

    return task;
  }

  // Enviar tarea por voz
  async sendVoiceTask(): Promise<void> {
    return new Promise((resolve, reject) => {
      const started = voiceService.startListening(
        async (transcript: string) => {
          await this.sendTask(transcript);
          resolve();
        },
        (err: string) => reject(new Error(err)),
      );
      if (!started) reject(new Error("Voz no disponible"));
    });
  }

  // Actualizar app AME via el agente
  async requestOTAUpdate(): Promise<AgentTask> {
    return this.sendTask(
      "Ejecuta python scripts/deploy_ame.py ota y reporta el resultado",
    );
  }

  // Revisar codigo del proyecto
  async reviewCode(filePath: string): Promise<AgentTask> {
    return this.sendTask(
      `Lee y revisa el archivo ${filePath}, detecta errores y sugiere mejoras`,
    );
  }

  // Ejecutar comando en Termux via el agente
  async runTermuxCommand(command: string): Promise<AgentTask> {
    return this.sendTask(`Ejecuta en Termux: ${command}`);
  }

  // Health check completo
  async fullHealthCheck(): Promise<AgentTask> {
    return this.sendTask(
      "Ejecuta python scripts/health_check.py y dime el resultado completo",
    );
  }

  setApiKey(key: string): void {
    this.apiKey = key;
    localStorage.setItem("gemini_api_key", key);
  }

  getTasks(): AgentTask[] {
    return this.tasks;
  }
  getPendingTasks(): AgentTask[] {
    return this.tasks.filter((t) => t.status !== "done");
  }
  onChange(cb: (tasks: AgentTask[]) => void): void {
    this.listeners.push(cb);
  }

  private updateTask(payload: any): void {
    const task = this.tasks.find((t) => t.id === payload.task_id);
    if (task) {
      task.status = "running";
      this.notify();
    }
  }

  private completeTask(payload: any): void {
    const task = this.tasks.find((t) => t.id === payload.task_id);
    if (task) {
      task.status = payload.error ? "error" : "done";
      task.result = payload.result || payload.error;
      this.notify();
      // Responder por voz si el resultado es corto
      if (task.result && task.result.length < 200) {
        voiceService.speak(task.result);
      }
    }
  }

  private addStep(payload: any): void {
    const task = this.tasks.find((t) => t.id === payload.task_id);
    if (task) {
      task.steps.push({
        tool: payload.tool,
        args: payload.args || {},
        result: payload.result,
        status: payload.error ? "error" : "ok",
      });
      this.notify();
    }
  }

  private notify(): void {
    this.listeners.forEach((cb) => cb(this.tasks));
  }
}

export const ameAgentService = new AMEAgentService();
