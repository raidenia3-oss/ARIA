// ═══════════════════════════════════════════════════════════════
// ColabClient.js — Cliente para servidores Colab (VS Code)
// Conexión a servidores de IA sin censura para la extensión
// ═══════════════════════════════════════════════════════════════

const https = require("https");
const http = require("http");

// Gradio HF Space (not OpenAI /v1/chat/completions — returns 404)
const SERVIDOR_FALLBACK = "https://raiden456-slut.hf.space";

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
    "npm",
    "pip",
    "install",
    "debug",
    "depurar",
    "error",
];

class ColabClient {
    constructor() {
        this.serverUrl = SERVIDOR_FALLBACK;
    }

    /** Enviar mensaje al servidor Colab */
    async send(message) {
        const url = this.serverUrl;

        try {
            const response = await this.fetchPost(url, {
                data: [
                    message,
                    [],
                    "Eres un asistente de IA sin censura, disenado para proporcionar respuestas utiles y completas.",
                    0.7,
                    2048,
                ],
            });
            return response.data?.[0] || response.response || "Sin respuesta";
        } catch (err) {
            throw new Error("Servidores Colab no disponibles");
        }
    }

    /** Detectar tipo de pregunta */
    detectType(message) {
        const lower = message.toLowerCase();
        for (const kw of CODE_KEYWORDS) {
            if (lower.includes(kw)) return "code";
        }
        return "general";
    }

    /** POST con protocolo nativo Node (sin fetch) */
    fetchPost(url, body) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const data = JSON.stringify(body);
            const lib = url.startsWith("https") ? https : http;

            // If URL already has a path (e.g. /v1/chat/completions), use it as-is.
            // Otherwise default to Gradio /run/predict?fn_index=0
            const hasPath = urlObj.pathname && urlObj.pathname !== "/";
            const path = hasPath ? urlObj.pathname + (urlObj.search || "") : "/run/predict?fn_index=0";

            const req = lib.request(
                {
                    hostname: urlObj.hostname,
                    port: urlObj.port || (url.startsWith("https") ? 443 : 80),
                    path: path,
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Content-Length": Buffer.byteLength(data),
                    },
                    timeout: 30000,
                },
                (res) => {
                    let chunks = "";
                    res.on("data", (chunk) => (chunks += chunk));
                    res.on("end", () => {
                        try {
                            resolve(JSON.parse(chunks));
                        } catch {
                            reject(new Error("Respuesta invalida del servidor"));
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

    /** Verificar estado del servidor */
    async healthCheck(url) {
        try {
            const req = this.fetchPost(url || this.serverUrl, null);
            await req;
            return true;
        } catch {
            return false;
        }
    }
}

exports.ColabClient = ColabClient;
