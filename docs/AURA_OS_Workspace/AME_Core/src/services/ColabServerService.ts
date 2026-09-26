// ══════════════════════════════════════════════════════════════
// ColabServerService.ts — Gestiona servidores Colab IA sin Termux
// Almacena URLs, verifica estado, detecta tipo de pregunta
// ═══════════════════════════════════════════════════════════════

export type ServerStatusInfo = "active" | "inactive" | "checking";

export interface ServerStatusMap {
    active: boolean;
    lastCheck: number;
}

export interface ServerInfo {
    url: string;
    type: "code" | "general";
}

export type ServerMode = "auto" | "forceCode" | "forceGeneral";

type Listener = (status: ServerStatusMap) => void;

/** Palabras clave para detectar preguntas de código */
const CODE_KEYWORDS = [
    "código",
    "codigo",
    "script",
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
    "for ",
    "clase",
    "npm",
    "pip",
    "install",
    "debug",
    "depurar",
    "error",
    "excepción",
    "excepcion",
    "log",
    "consola",
];

export class ColabServerService {
    private static instance: ColabServerService;
    private listeners: Listener[] = [];
    private serverStatus: ServerStatusMap = { active: false, lastCheck: 0 };
    private checkInterval: ReturnType<typeof setInterval> | null = null;

    static getInstance(): ColabServerService {
        if (!ColabServerService.instance) {
            ColabServerService.instance = new ColabServerService();
        }
        return ColabServerService.instance;
    }

    private constructor() {
        // Iniciar chequeo periódico cada 30 segundos
        this.checkInterval = setInterval(() => this.checkServerStatus(), 30000);
    }

    // ─── Gestión de URLs (localStorage) ──────────────────────

    setServerUrl(serverUrl: string): void {
        localStorage.setItem("serverUrl", serverUrl);
    }

    getServerUrl(): string {
        return localStorage.getItem("serverUrl") || "https://raiden456-slut.hf.space";
    }

    // ─── Verificación de estado ──────────────────────────────

    async checkServerStatus(): Promise<ServerStatusMap> {
        const serverUrl = this.getServerUrl();
        const status = await this.pingServer(serverUrl);

        this.serverStatus = { active: status === "active", lastCheck: Date.now() };
        this.notifyListeners();
        return this.serverStatus;
    }

    getStatus(): ServerStatusMap {
        return this.serverStatus;
    }

    // ─── Detección de tipo de pregunta ───────────────────────

    detectQuestionType(question: string): "code" | "general" {
        const lower = question.toLowerCase();
        for (const kw of CODE_KEYWORDS) {
            if (lower.includes(kw)) return "code";
        }
        return "general";
    }

    // ─── Selección inteligente de servidor ───────────────────

    getAppropriateServerUrl(question: string, mode: ServerMode = "auto"): ServerInfo | null {
        const serverUrl = this.getServerUrl();
        if (!serverUrl) return null;

        let type: "code" | "general" = "general";
        if (mode === "forceCode" || (mode === "auto" && this.detectQuestionType(question) === "code")) {
            type = "code";
        }

        return { url: serverUrl, type };
    }

    onStatusChange(cb: Listener): () => void {
        this.listeners.push(cb);
        return () => {
            this.listeners = this.listeners.filter((l) => l !== cb);
        };
    }

    private async pingServer(url: string): Promise<ServerStatusInfo> {
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);
            const r = await fetch(`${url}/health`, {
                method: "GET",
                signal: controller.signal,
            });
            clearTimeout(timeout);
            return r.ok || r.status < 500 ? "active" : "inactive";
        } catch {
            return "inactive";
        }
    }

    private notifyListeners(): void {
        this.listeners.forEach((cb) => cb(this.serverStatus));
    }

    destroy(): void {
        if (this.checkInterval) clearInterval(this.checkInterval);
    }
}

export const colabServerService = ColabServerService.getInstance();
