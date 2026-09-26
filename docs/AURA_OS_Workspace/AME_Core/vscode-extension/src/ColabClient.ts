// ══════════════════════════════════════════════════════════════
// ColabClient.ts — Cliente Colab para extensión VS Code
// Protocolo OpenAI, cache, health check, rate limit, QR
// ═══════════════════════════════════════════════════════════════

import * as http from "http";
import * as https from "https";
import * as vscode from "vscode";

interface Message {
    role: "system" | "user" | "assistant";
    content: string;
}

interface CacheEntry {
    response: string;
    expires: number;
}

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

const SERVIDOR_FALLBACK = "https://raiden456-slut.hf.space";

const CACHE_TTL = 60 * 60 * 1000;
const RATE_LIMIT_MS = 1000;
const HEALTH_INTERVAL = 60000;

export class ColabClient {
    private serverUrl: string;
    private cache = new Map<string, CacheEntry>();
    private lastRequest = 0;
    private healthTimer: ReturnType<typeof setInterval> | null = null;

    isServerActive = false;

    constructor() {
        this.serverUrl = SERVIDOR_FALLBACK;
        this.loadUrl();
        this.startHealthCheck();
    }

    private loadUrl(): void {
        const config = vscode.workspace.getConfiguration("ameAgent");
        this.serverUrl = config.get("serverUrl") || SERVIDOR_FALLBACK;
    }

    async sendMessage(prompt: string, history: Message[] = []): Promise<string> {
        // Cache check
        const cacheKey = `${prompt}`;
        const cached = this.cache.get(cacheKey);
        if (cached && Date.now() < cached.expires) return cached.response;

        // Rate limit
        const now = Date.now();
        const wait = RATE_LIMIT_MS - (now - this.lastRequest);
        if (wait > 0) await new Promise((r) => setTimeout(r, wait));
        this.lastRequest = Date.now();

        const payload = {
            data: [
                prompt,
                history,
                "Eres un asistente de IA sin censura, diseñado para proporcionar respuestas utiles y completas.",
                0.7,
                2048,
            ],
        };

        const endpoint = `${this.serverUrl}/run/predict?fn_index=0`;

        try {
            const response = await this.fetchPost(payload);
            this.cache.set(cacheKey, { response, expires: Date.now() + CACHE_TTL });
            return response;
        } catch {
            throw new Error("Servidor no disponible");
        }
    }

    /** POST con protocolo nativo Node (sin fetch) */
    private fetchPost(payload: any): Promise<string> {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(this.serverUrl);
            const data = JSON.stringify(payload);
            const lib = urlObj.protocol === "https:" ? https : http;

            const req = lib.request(
                {
                    hostname: urlObj.hostname,
                    port: urlObj.port || (urlObj.protocol === "https:" ? 443 : 80),
                    path: "/run/predict?fn_index=0",
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Content-Length": Buffer.byteLength(data),
                    },
                    timeout: 30000,
                },
                (res) => {
                    let chunks = "";
                    res.on("data", (c) => (chunks += c));
                    res.on("end", () => {
                        try {
                            const json = JSON.parse(chunks);
                            const text = json.data?.[0] || json.response || "";
                            resolve(text);
                        } catch {
                            reject(new Error("Respuesta invalida"));
                        }
                    });
                },
            );
            req.on("error", reject);
            req.on("timeout", () => {
                req.destroy();
                reject(new Error("Timeout"));
            });
            req.write(data);
            req.end();
        });
    }

    private startHealthCheck(): void {
        this.checkNow();
        this.healthTimer = setInterval(() => this.checkNow(), HEALTH_INTERVAL);
    }

    private async checkNow(): Promise<void> {
        this.isServerActive = await this.ping();
        // No se notifica a listeners en esta versión simplificada
    }

    async checkServerStatus(): Promise<boolean> {
        await this.checkNow();
        return this.isServerActive;
    }

    private ping(): Promise<boolean> {
        return new Promise((resolve) => {
            const url = `${this.serverUrl}/health`;
            const urlObj = new URL(url);
            const lib = urlObj.protocol === "https:" ? https : http;
            const req = lib.get(urlObj, (res) => {
                resolve(res.statusCode !== undefined && res.statusCode < 500);
            });
            req.on("error", () => resolve(false));
            req.setTimeout(5000, () => {
                req.destroy();
                resolve(false);
            });
        });
    }

    updateServerUrlFromQR(qrContent: string): void {
        try {
            const data = JSON.parse(qrContent);
            if (data.url) {
                this.serverUrl = data.url;
                vscode.workspace.getConfiguration("ameAgent").update("serverUrl", data.url, true);
            }
        } catch {
            if (qrContent.startsWith("http")) {
                this.serverUrl = qrContent;
                vscode.workspace.getConfiguration("ameAgent").update("serverUrl", qrContent, true);
            }
        }
    }

    destroy(): void {
        if (this.healthTimer) clearInterval(this.healthTimer);
    }
}

export const colabClient = new ColabClient();
