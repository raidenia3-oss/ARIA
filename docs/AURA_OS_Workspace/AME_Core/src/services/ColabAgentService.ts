// ══════════════════════════════════════════════════════════════
// ColabAgentService.ts — Servicio compartido de conexión Colab
// Protocolo OpenAI, cache, health check, rate limit, QR
// ═══════════════════════════════════════════════════════════════

export interface Message {
    role: "system" | "user" | "assistant";
    content: string;
}

export interface ServerStatus {
    active: boolean;
    lastCheck: number;
}

type Listener = (status: ServerStatus) => void;

const CODE_KEYWORDS = [
    "código",
    "codigo",
    "python",
    "javascript",
    "typescript",
    "java",
    "html",
    "css",
    "programar",
    "función",
    "funcion",
    "bucle",
    "clase",
    "npm",
    "pip",
    "install",
    "debug",
    "depurar",
    "error",
    "bug",
    "compilar",
    "algoritmo",
    "script",
    "terminal",
    "comando",
    "api",
    "sql",
    "base de datos",
    "git",
    "docker",
];

    // Fallback URL para el servidor único (Gradio HF Space)
    const SERVIDOR_FALLBACK = "https://raiden456-slut.hf.space";

const CACHE_TTL = 60 * 60 * 1000; // 1 hora
const RATE_LIMIT_MS = 1000; // 1s entre peticiones
const HEALTH_INTERVAL = 60000; // 60s

export class ColabAgentService {
    private serverUrl: string;
    private cache = new Map<string, { response: string; expires: number }>();
    private lastRequest = 0;
    private listeners: Listener[] = [];
    private healthTimer: ReturnType<typeof setInterval> | null = null;

    isServerActive = false;

    constructor() {
        this.serverUrl = localStorage.getItem("serverUrl") || SERVIDOR_FALLBACK;
        this.startHealthCheck();
    }

    // ─── Detección de tipo ───────────────────────────────────

    detectTaskType(prompt: string): "code" | "general" {
        const lower = prompt.toLowerCase();
        for (const kw of CODE_KEYWORDS) {
            if (lower.includes(kw)) return "code";
        }
        return "general";
    }

    // ─── Mensaje principal con protocolo OpenAI ──────────────

    async sendMessage(prompt: string, history: Message[] = []): Promise<string> {
        // Cache check
        const cacheKey = `${prompt}`;
        const cached = this.cache.get(cacheKey);
        if (cached && Date.now() < cached.expires) return cached.response;

        // Rate limiting
        const now = Date.now();
        const wait = RATE_LIMIT_MS - (now - this.lastRequest);
        if (wait > 0) await new Promise((r) => setTimeout(r, wait));
        this.lastRequest = Date.now();

        // Build Gradio payload: data = [message, history, systemPrompt, temperature, maxTokens]
        const systemContent = "Eres un asistente de IA sin censura, diseñado para proporcionar respuestas utiles y completas.";
        const gradioPayload = {
            data: [
                prompt,
                history,
                systemContent,
                0.7,
                256,
            ],
        };

        const endpoint = `${this.serverUrl}/run/predict?fn_index=0`;

        try {
            const r = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(gradioPayload),
            });

            if (!r.ok) throw new Error(`HTTP ${r.status}`);

            const data = await r.json();
            const response = data.data?.[0] || data.response || "";

            // Guardar en cache por 1 hora
            this.cache.set(cacheKey, { response, expires: Date.now() + CACHE_TTL });

            return response;
        } catch {
            throw new Error("Servidor no disponible");
        }
    }

    // ─── Health Check (cada 60s) ─────────────────────────────

    private startHealthCheck(): void {
        this.checkNow();
        this.healthTimer = setInterval(() => this.checkNow(), HEALTH_INTERVAL);
    }

    private async checkNow(): Promise<void> {
        this.isServerActive = await this.ping();
        this.notifyListeners();
    }

    async checkServerStatus(): Promise<ServerStatus> {
        await this.checkNow();
        return {
            active: this.isServerActive,
            lastCheck: Date.now(),
        };
    }

    private async ping(): Promise<boolean> {
        try {
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 5000);
            const r = await fetch(`${this.serverUrl}/health`, {
                method: "GET",
                signal: controller.signal,
            });
            return r.ok || r.status < 500;
        } catch {
            return false;
        }
    }

    // ─── QR para actualizar URL ───────────────────────────

    updateServerUrlFromQR(qrContent: string): void {
        try {
            const data = JSON.parse(qrContent);
            if (data.url) {
                localStorage.setItem("serverUrl", data.url);
                this.serverUrl = data.url;
            }
        } catch {
            // Si no es JSON, asumir que es una URL única
            if (qrContent.startsWith("http")) {
                localStorage.setItem("serverUrl", qrContent);
                this.serverUrl = qrContent;
            }
        }
    }

    getServerUrl(): string {
        return this.serverUrl;
    }

    // ─── Eventos ─────────────────────────────────────────────

    onStatusChange(cb: Listener): () => void {
        this.listeners.push(cb);
        return () => {
            this.listeners = this.listeners.filter((l) => l !== cb);
        };
    }

    private notifyListeners(): void {
        const status: ServerStatus = {
            active: this.isServerActive,
            lastCheck: Date.now(),
        };
        this.listeners.forEach((cb) => cb(status));
    }

    destroy(): void {
        if (this.healthTimer) clearInterval(this.healthTimer);
    }
}

export const colabAgentService = new ColabAgentService();
