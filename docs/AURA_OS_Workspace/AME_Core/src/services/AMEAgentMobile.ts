// ═══════════════════════════════════════════════════════════════
// AMEAgentMobile.ts — Agente autónomo móvil del ecosistema AURA
// Usa servidores Colab para IA, cola de tareas, memoria persistente
// ═══════════════════════════════════════════════════════════════

import { auraService } from "./AURAService";
import { colabServerService } from "./ColabServerService";

export interface AgentMessage {
    role: "user" | "assistant";
    content: string;
    type?: "code" | "general";
    timestamp: number;
}

export interface AgentTask {
    id: string;
    prompt: string;
    status: "pending" | "processing" | "done" | "failed";
    type: "code" | "general";
    maxRetries: number;
    attempts: number;
    result?: string;
}

export type TaskHandler = (task: AgentTask) => Promise<string>;

/** Respuestas offline básicas cuando no hay servidores */
const OFFLINE_RESPONSES: Record<string, string> = {
    default: "No hay servidores disponibles. Conéctate a Colab o configura redes.",
    code: "No puedo ejecutar código ahora. Sin conexión a servidores IA.",
    help: "Modo offline. Usa QR para conectar servidores Colab.",
};

/** Prefijo de localStorage para memoria */
const MEMORY_KEY = "ame_agent_memory";

export class AMEAgentMobile {
    private memory: AgentMessage[] = [];
    private taskQueue: AgentTask[] = [];
    private processing = false;
    private taskHandlers = new Map<string, TaskHandler>();
    private listeners: Array<(msg: AgentMessage) => void> = [];

    constructor() {
        this.loadMemory();
        this.registerDefaultHandlers();
    }

    // ─── Memoria persistente ─────────────────────────────────

    private loadMemory(): void {
        try {
            const raw = localStorage.getItem(MEMORY_KEY);
            if (raw) this.memory = JSON.parse(raw);
        } catch {
            this.memory = [];
        }
    }

    private saveMemory(): void {
        localStorage.setItem(MEMORY_KEY, JSON.stringify(this.memory.slice(-50)));
    }

    getMemory(): AgentMessage[] {
        return [...this.memory];
    }

    clearMemory(): void {
        this.memory = [];
        this.saveMemory();
    }

    // ─── Procesar mensaje (entrada principal) ────────────────

    async processMessage(content: string): Promise<AgentMessage> {
        const userMsg: AgentMessage = {
            role: "user",
            content,
            timestamp: Date.now(),
        };
        this.memory.push(userMsg);
        this.saveMemory();

        const type = colabServerService.detectQuestionType(content);
        const serverUrl = colabServerService.getAppropriateServerUrl(content);

        let response: string;

        if (serverUrl) {
            try {
                response = await this.callColab(serverUrl.url, content, serverUrl.type);
            } catch {
                response = await this.processFallback(content);
            }
        } else {
            response = await this.processFallback(content);
        }

        const assistantMsg: AgentMessage = {
            role: "assistant",
            content: response,
            type: type,
            timestamp: Date.now(),
        };
        this.memory.push(assistantMsg);
        this.saveMemory();
        this.notifyListeners(assistantMsg);
        return assistantMsg;
    }

    private async callColab(
        url: string,
        prompt: string,
        type: "code" | "general",
    ): Promise<string> {
        // Gradio HF Space endpoint: /run/predict?fn_index=0
        // data = [message, history, systemPrompt, temperature, maxTokens]
        const r = await fetch(`${url}/run/predict?fn_index=0`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                data: [prompt, [], "", 0.7, 256],
            }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        return data.data?.[0] || data.response || "Sin respuesta";
    }

    private async processFallback(content: string): Promise<string> {
        const lower = content.toLowerCase();
        if (lower.includes("ayuda") || lower.includes("help")) return OFFLINE_RESPONSES.help;
        if (lower.includes("código") || lower.includes("codigo")) return OFFLINE_RESPONSES.code;
        return OFFLINE_RESPONSES.default;
    }

    // ─── Sistema de cola de tareas ───────────────────────────

    enqueueTask(prompt: string, type: "code" | "general"): string {
        const id = `task_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
        this.taskQueue.push({
            id,
            prompt,
            status: "pending",
            type,
            maxRetries: 3,
            attempts: 0,
        });
        this.processQueue();
        return id;
    }

    private async processQueue(): Promise<void> {
        if (this.processing) return;
        this.processing = true;

        while (this.taskQueue.length > 0) {
            const task = this.taskQueue[0];
            task.status = "processing";

            const server = colabServerService.getAppropriateServerUrl(
                task.prompt,
                task.type === "code" ? "forceCode" : "forceGeneral",
            );

            if (server) {
                try {
                    task.result = await this.callColab(server.url, task.prompt, server.type);
                    task.status = "done";
                } catch {
                    task.attempts++;
                    if (task.attempts < task.maxRetries) {
                        task.status = "pending";
                        await new Promise((r) => setTimeout(r, 2000 * task.attempts));
                        continue; // Reintentar
                    }
                    task.status = "failed";
                    task.result = "Falló tras " + task.maxRetries + " intentos";
                }
            } else {
                task.status = "failed";
                task.result = OFFLINE_RESPONSES.default;
            }

            this.taskQueue.shift(); // Remover tarea procesada
        }

        this.processing = false;
    }

    getQueue(): AgentTask[] {
        return [...this.taskQueue];
    }

    registerHandler(name: string, handler: TaskHandler): void {
        this.taskHandlers.set(name, handler);
    }

    // ─── Acciones del agente ─────────────────────────────────

    async sendToAura(event: string, payload: unknown = {}): Promise<void> {
        auraService.send(event, payload);
    }

    async searchWeb(query: string): Promise<string> {
        try {
            auraService.send("SEARCH_REQUEST", { query });
            return `Búsqueda enviada: "${query}" (pendiente de respuesta AURA)`;
        } catch {
            return "Error al enviar búsqueda";
        }
    }

    async readFile(path: string): Promise<string> {
        try {
            const mod = await import("@capacitor/filesystem");
            const r = await mod.Filesystem.readFile({ path });
            return typeof r.data === "string" ? r.data : JSON.stringify(r.data);
        } catch {
            return `No se pudo leer: ${path}`;
        }
    }

    async writeFile(path: string, data: string): Promise<string> {
        try {
            const mod = await import("@capacitor/filesystem");
            await mod.Filesystem.writeFile({ path, data });
            return `Archivo escrito: ${path}`;
        } catch {
            return `Error escribiendo: ${path}`;
        }
    }

    async sendNotification(title: string, body: string): Promise<void> {
        try {
            const mod = await import("@capacitor/local-notifications");
            await mod.LocalNotifications.schedule({
                notifications: [{ title, body, id: Date.now() }],
            });
        } catch {
            console.log("Notificaciones no disponibles");
        }
    }

    // ─── Eventos ─────────────────────────────────────────────

    onMessage(cb: (msg: AgentMessage) => void): void {
        this.listeners.push(cb);
    }

    private notifyListeners(msg: AgentMessage): void {
        this.listeners.forEach((cb) => cb(msg));
    }

    private registerDefaultHandlers(): void {
        this.registerHandler("help", async () => "Comandos: /help, /clear, /status, /search");
    }
}

export const ameAgentMobile = new AMEAgentMobile();
