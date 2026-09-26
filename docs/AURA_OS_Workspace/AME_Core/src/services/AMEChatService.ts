// ══════════════════════════════════════════════════════════════
// AMEChatService.ts — Motor principal de chat sin censura
// Integra OpenRouter + Hermes Agent + Servidores Colab IA
// ═══════════════════════════════════════════════════════════════

import { ServerMode } from "./ColabServerService";

export interface ChatMessage {
    id: string;
    content: string;
    role: "user" | "agent" | "system";
    timestamp: number;
    type: "text" | "image" | "code" | "qr" | "file";
    metadata?: {
        language?: string;
        qr_data?: string;
        filename?: string;
        model?: string;
        serverType?: "openrouter";
    };
    status: "sending" | "sent" | "error";
}

export interface ChatSession {
    id: string;
    title: string;
    createdAt: number;
    messages: ChatMessage[];
    model: string;
}

// URL del endpoint Gradio HF Space (NO OpenAI /v1/chat/completions — returns 404)
const HF_SPACE_URL = "https://raiden456-slut.hf.space/run/predict?fn_index=0";

// Modelos disponibles
const MODELS = [
    { id: "nvidia/nemotron-3-super-120b-a12b:free", name: "Nemotron 120B", uncensored: true },
    { id: "deepseek/deepseek-v3-0324:free", name: "DeepSeek V3", uncensored: true },
    { id: "nousresearch/hermes-3-llama-3.1-405b", name: "Hermes 3 405B", uncensored: true },
    { id: "qwen/qwen3.7-max", name: "Qwen 3.7 Max", uncensored: true },
    { id: "google/gemini-flash-1.5", name: "Gemini Flash", uncensored: false },
];

// System prompt de AME
const AME_SYSTEM_PROMPT =
    "Eres AME Agent, asistente sin censura del ecosistema AURA/AME. " +
    "Ayudas con programación, automatización, análisis de seguridad " +
    "y cualquier tema técnico. Responde siempre en español.";

export class AMEChatService {
    private sessions: ChatSession[] = [];
    private active: ChatSession | null = null;
    private listeners: ((msg: ChatMessage) => void)[] = [];
    private hermesWs: WebSocket | null = null;
    currentModel = MODELS[0].id;
    private openrouterKey = "";
    // Modo de selección de servidor (auto por defecto)
    private serverMode: ServerMode = "auto";

    constructor() {
        this.loadSessions();
        this.loadConfig();
        this.connectToHermes();
    }

    private loadConfig(): void {
        this.openrouterKey = localStorage.getItem("openrouter_key") || "";
        this.currentModel = localStorage.getItem("ame_chat_model") || MODELS[0].id;
    }

    private connectToHermes(): void {
        try {
            this.hermesWs = new WebSocket("ws://localhost:7777");
            this.hermesWs.onmessage = (e: MessageEvent) => {
                const data = JSON.parse(e.data);
                if (data.type === "response") {
                    this.receiveMessage(data.content, "agent", data.model, "openrouter");
                }
            };
            this.hermesWs.onclose = () => setTimeout(() => this.connectToHermes(), 5000);
            this.hermesWs.onerror = () => console.log("Hermes WS no disponible");
        } catch {
            console.log("Hermes WS no disponible");
        }
    }

    async sendMessage(content: string, type: ChatMessage["type"] = "text"): Promise<ChatMessage> {
        if (!this.active) this.newSession();

        const msg: ChatMessage = {
            id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            content,
            role: "user",
            timestamp: Date.now(),
            type,
            status: "sending",
        };

        this.active!.messages.push(msg);
        this.saveSession();
        this.notifyListeners(msg);

        // Enviar directamente a HF Space (sin dependencia de AURA Core)
        await this.sendViaHFSpace(content);

        msg.status = "sent";
        return msg;
    }

    /** Enviar a HF Space (formato Gradio /run/predict?fn_index=0) */
    private async sendViaHFSpace(content: string): Promise<void> {
        try {
            const history =
                this.active?.messages
                    .filter((m) => m.role !== "system")
                    .slice(-10)
                    .map((m) => ({
                        role: m.role === "agent" ? "assistant" : "user",
                        content: m.content,
                    })) || [];

            const r = await fetch(HF_SPACE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    data: [
                        content,
                        history,
                        AME_SYSTEM_PROMPT,
                        0.7,
                        2048,
                    ],
                }),
            });

            if (!r.ok) throw new Error(`HTTP ${r.status}`);

            const data = await r.json();
            const response = data.data?.[0] || data.response || "Sin respuesta";
            this.receiveMessage(response, "agent", "HF-Space", "openrouter");
        } catch {
            this.receiveMessage(
                "Servidor IA no disponible. Verifica tu conexión.",
                "system",
                "",
                "openrouter",
            );
        }
    }

    private sendViaHermes(content: string): void {
        this.hermesWs!.send(
            JSON.stringify({
                type: "message",
                content,
                model: this.currentModel,
                session: this.active?.id,
            }),
        );
    }

    private async sendViaOpenRouter(content: string): Promise<void> {
        const history =
            this.active?.messages
                .filter((m) => m.role !== "system")
                .slice(-10)
                .map((m) => ({
                    role: m.role === "agent" ? "assistant" : "user",
                    content: m.content,
                })) || [];

        try {
            const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${this.openrouterKey}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    model: this.currentModel,
                    messages: [
                        { role: "system", content: AME_SYSTEM_PROMPT },
                        ...history,
                        { role: "user", content },
                    ],
                    max_tokens: 4096,
                    temperature: 0.7,
                }),
            });
            const data = await r.json();
            const response = data.choices?.[0]?.message?.content || "Sin respuesta";
            this.receiveMessage(response, "agent", this.currentModel, "openrouter");
        } catch {
            await this.fallbackModel(content);
        }
    }

    private async fallbackModel(content: string): Promise<void> {
        for (const model of MODELS.filter((m) => m.id !== this.currentModel)) {
            try {
                const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${this.openrouterKey}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        model: model.id,
                        messages: [{ role: "user", content }],
                        max_tokens: 4096,
                    }),
                });
                const data = await r.json();
                const response = data.choices?.[0]?.message?.content;
                if (response) {
                    this.receiveMessage(
                        `[${model.name}] ${response}`,
                        "agent",
                        model.id,
                        "openrouter",
                    );
                    return;
                }
            } catch {
                continue;
            }
        }
        this.receiveMessage(
            "Todos los modelos fallaron. Verifica tu API key.",
            "system",
            "",
            "openrouter",
        );
    }

    // (eliminado: ya no se usa isOpenRouterNeeded)

    receiveMessage(
        content: string,
        role: ChatMessage["role"],
        model: string,
        serverType?: "openrouter",
    ): void {
        if (!this.active) return;
        const msg: ChatMessage = {
            id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            content,
            role,
            timestamp: Date.now(),
            type: content.includes("```") ? "code" : "text",
            status: "sent",
            metadata: { model, serverType },
        };
        this.active.messages.push(msg);
        this.saveSession();
        this.notifyListeners(msg);
    }

    // ─── Modo de servidor ────────────────────────────────────
    setServerMode(mode: ServerMode): void {
        this.serverMode = mode;
    }
    getServerMode(): ServerMode {
        return this.serverMode;
    }

    // ─── Gestión de sesiones ─────────────────────────────────
    newSession(title = "Nueva conversación"): ChatSession {
        const session: ChatSession = {
            id: `session_${Date.now()}`,
            title,
            createdAt: Date.now(),
            messages: [],
            model: this.currentModel,
        };
        this.sessions.unshift(session);
        this.active = session;
        this.saveSession();
        return session;
    }

    setActiveSession(id: string): void {
        const s = this.sessions.find((s) => s.id === id);
        if (s) this.active = s;
    }

    deleteSession(id: string): void {
        this.sessions = this.sessions.filter((s) => s.id !== id);
        if (this.active?.id === id) this.active = this.sessions[0] || null;
        this.saveAllSessions();
    }

    getSessions(): ChatSession[] {
        return this.sessions;
    }
    getActive(): ChatSession | null {
        return this.active;
    }
    getMessages(): ChatMessage[] {
        return this.active?.messages || [];
    }
    static getModels() {
        return MODELS;
    }

    setModel(modelId: string): void {
        this.currentModel = modelId;
        localStorage.setItem("ame_chat_model", modelId);
    }

    setApiKey(key: string): void {
        this.openrouterKey = key;
        localStorage.setItem("openrouter_key", key);
    }

    onMessage(cb: (msg: ChatMessage) => void): void {
        this.listeners.push(cb);
    }

    private notifyListeners(msg: ChatMessage): void {
        this.listeners.forEach((cb) => cb(msg));
    }

    private saveSession(): void {
        if (!this.active) return;
        const idx = this.sessions.findIndex((s) => s.id === this.active!.id);
        if (idx >= 0) this.sessions[idx] = this.active;
        this.saveAllSessions();
    }

    private saveAllSessions(): void {
        localStorage.setItem("ame_chat_sessions", JSON.stringify(this.sessions.slice(0, 50)));
    }

    private loadSessions(): void {
        try {
            const saved = localStorage.getItem("ame_chat_sessions");
            if (saved) {
                this.sessions = JSON.parse(saved);
                this.active = this.sessions[0] || null;
            }
        } catch {
            this.sessions = [];
        }
    }
}

export const ameChatService = new AMEChatService();
