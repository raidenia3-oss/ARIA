/**
 * services.config.js - Configuración centralizada de micro-servicios AURA
 *
 * Este archivo centraliza todas las URLs y endpoints de los servicios.
 * Para agregar un nuevo servicio, simplemente añade una nueva entrada en SERVICES.
 */

const SERVICES = {
    // ========== API PRINCIPAL ==========
    API_URL: "https://api.aura-system.com",
    API_FALLBACK: "https://aura-api.railway.app",

    // ========== INTELIGENCIA ARTIFICIAL ==========
    AI_CORE_URL: "https://huggingface.co/api",
    AI_CORE_FALLBACK: "https://api-inference.huggingface.co",
    AI_CORE_SECONDARY: "https://local-ai.aura-system.com:11434",
    AI_MODEL_PRIMARY: "meta-llama/Llama-2-70b-chat-hf",
    AI_MODEL_SECONDARY: "mistral/mixtral-8x7b-instruct-v0.1",
    AI_MODEL_LOCAL: "llama2",

    // ========== MONETIZACIÓN Y ANÁLISIS ==========
    AD_NETWORK_URL: "https://ads.aura-system.com",
    ANALYTICS_URL: "https://analytics.aura-system.com",
    AD_FALLBACK: "https://backup-ads.aura-system.com",

    // ========== DATOS EN TIEMPO REAL ==========
    DATA_FEED_URL: "https://data-feed.aura-system.com",
    WEBSOCKET_URL: "wss://ws.aura-system.com",
    WEBSOCKET_FALLBACK: "wss://aura-server-01.vercel.app",

    // ========== ALMACENAMIENTO ==========
    STORAGE_URL: "https://storage.aura-system.com",
    FILE_UPLOAD_URL: "https://upload.aura-system.com",

    // ========== NOTIFICACIONES ==========
    NOTIFICATION_URL: "https://notifications.aura-system.com",
    PUSH_URL: "https://push.aura-system.com",

    // ========== SERVICIOS ADICIONALES ==========
    // Para agregar un nuevo servicio, sigue este formato:
    // SERVICIO_NOMBRE_URL: "https://servicio.aura-system.com",
};

/**
 * Configuración de failover y resiliencia
 */
const RESILIENCE_CONFIG = {
    // Tiempo máximo de espera para una respuesta (ms)
    TIMEOUT: 10000,

    // Número máximo de reintentos
    MAX_RETRIES: 3,

    // Delay entre reintentos (ms)
    RETRY_DELAY: 1000,

    // Backoff exponencial: true = 1s, 2s, 4s; false = delay fijo
    EXPONENTIAL_BACKOFF: true,

    // Umbral de salud del servicio (0-1)
    HEALTH_THRESHOLD: 0.7,
};

/**
 * Historial de servicios para métricas
 */
const SERVICE_HISTORY = {
    // Estructura: {
    //   "service_name": {
    //     successes: 0,
    //     failures: 0,
    //     lastChecked: null,
    //     status: "healthy" | "degraded" | "down"
    //   }
    // }
};

/**
 * Obtiene la URL de un servicio con fallback automático
 * @param {string} primary - URL principal
 * @param {string} fallback - URL de respaldo
 * @returns {string} URL a usar
 */
function getServiceUrl(primary, fallback) {
    const serviceName = primary.split("//")[1]?.split("/")[0] || primary;
    const history = SERVICE_HISTORY[serviceName];

    if (history && history.status === "down" && fallback) {
        console.warn(`[ServicesConfig] ${serviceName} está degradado, usando fallback`);
        return fallback;
    }

    return primary;
}

/**
 * Marca un servicio como saludable o degradado
 * @param {string} serviceUrl - URL del servicio
 * @param {boolean} success - Si la llamada fue exitosa
 */
function recordServiceHealth(serviceUrl, success) {
    const serviceName = serviceUrl.split("//")[1]?.split("/")[0] || serviceUrl;

    if (!SERVICE_HISTORY[serviceName]) {
        SERVICE_HISTORY[serviceName] = {
            successes: 0,
            failures: 0,
            lastChecked: new Date().toISOString(),
            status: "healthy",
        };
    }

    const history = SERVICE_HISTORY[serviceName];
    history.lastChecked = new Date().toISOString();

    if (success) {
        history.successes++;
        history.status = "healthy";
    } else {
        history.failures++;
        const total = history.successes + history.failures;
        const health = history.successes / total;

        if (health < RESILIENCE_CONFIG.HEALTH_THRESHOLD) {
            history.status = "degraded";
        } else if (health < 0.5) {
            history.status = "down";
        }
    }
}

/**
 * Obtiene el estado de salud de todos los servicios
 * @returns {Object} Estado de cada servicio
 */
function getServicesHealth() {
    const health = {};

    for (const [name, history] of Object.entries(SERVICE_HISTORY)) {
        const total = history.successes + history.failures;
        health[name] = {
            status: history.status,
            health: total > 0 ? history.successes / total : 0,
            successRate: total > 0 ? ((history.successes / total) * 100).toFixed(2) + "%" : "N/A",
            lastChecked: history.lastChecked,
        };
    }

    return health;
}

/**
 * Reinicia el historial de un servicio
 * @param {string} serviceUrl - URL del servicio
 */
function resetServiceHealth(serviceUrl) {
    const serviceName = serviceUrl.split("//")[1]?.split("/")[0] || serviceUrl;
    delete SERVICE_HISTORY[serviceName];
    console.log(`[ServicesConfig] Historial reiniciado para ${serviceName}`);
}

/**
 * Cliente HTTP con failover automático
 */
class ResilientHttpClient {
    constructor() {
        this.baseHeaders = {
            "Content-Type": "application/json",
            Accept: "application/json",
        };
    }

    /**
     * Realiza una petición GET con failover
     * @param {string} endpoint - Endpoint del servicio
     * @param {Object} options - Opciones adicionales
     * @returns {Promise<Response>}
     */
    async get(endpoint, options = {}) {
        const primaryUrl = getServiceUrl(endpoint, options.fallback);
        const fallbackUrl = options.fallback || null;

        return await this._requestWithFailover("GET", primaryUrl, fallbackUrl, options);
    }

    /**
     * Realiza una petición POST con failover
     * @param {string} endpoint - Endpoint del servicio
     * @param {Object} body - Cuerpo de la petición
     * @param {Object} options - Opciones adicionales
     * @returns {Promise<Response>}
     */
    async post(endpoint, body, options = {}) {
        const primaryUrl = getServiceUrl(endpoint, options.fallback);
        const fallbackUrl = options.fallback || null;

        return await this._requestWithFailover("POST", primaryUrl, fallbackUrl, {
            ...options,
            body: JSON.stringify(body),
        });
    }

    /**
     * Ejecuta la petición con lógica de failover
     */
    async _requestWithFailover(method, primaryUrl, fallbackUrl, options = {}) {
        let lastError = null;
        const urls = [primaryUrl];
        if (fallbackUrl) urls.push(fallbackUrl);

        for (let attempt = 0; attempt < RESILIENCE_CONFIG.MAX_RETRIES; attempt++) {
            for (const url of urls) {
                try {
                    const controller = new AbortController();
                    const timeout = setTimeout(() => controller.abort(), RESILIENCE_CONFIG.TIMEOUT);

                    const response = await fetch(url, {
                        method,
                        headers: { ...this.baseHeaders, ...options.headers },
                        body: options.body,
                        signal: controller.signal,
                        mode: "cors",
                        credentials: "same-origin",
                    });

                    clearTimeout(timeout);

                    if (response.ok) {
                        recordServiceHealth(url, true);
                        return response;
                    }

                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                } catch (error) {
                    lastError = error;
                    recordServiceHealth(url, false);

                    const delay = RESILIENCE_CONFIG.EXPONENTIAL_BACKOFF
                        ? RESILIENCE_CONFIG.RETRY_DELAY * Math.pow(2, attempt)
                        : RESILIENCE_CONFIG.RETRY_DELAY;

                    console.warn(`[ResilientClient] Error en ${url}, reintento en ${delay}ms`);
                    await new Promise((resolve) => setTimeout(resolve, delay));
                }
            }
        }

        throw lastError || new Error("Todos los servicios fallaron");
    }

    /**
     * Obtiene el estado de salud de todos los servicios
     */
    getHealthStatus() {
        return getServicesHealth();
    }

    /**
     * Reinicia el historial de un servicio
     */
    resetHealth(serviceUrl) {
        resetServiceHealth(serviceUrl);
    }
}

// ========== EXPORTAR API PÚBLICA ==========
window.AURA_ServicesConfig = {
    SERVICES,
    RESILIENCE_CONFIG,
    getServiceUrl,
    recordServiceHealth,
    getServicesHealth,
    resetServiceHealth,
    ResilientHttpClient,
};

// Log de inicialización
console.log("[ServicesConfig] Micro-servicios configurados:", Object.keys(SERVICES).length);
console.log("[ServicesConfig] Modo resiliencia activado");
