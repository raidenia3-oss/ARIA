/**
 * AURA Services Configuration & Resilience Layer
 * Orquestador de configuración y Circuit Breaker para HF Space / Railway
 */

const AURA_CONFIG = {
    RAILWAY_WS_URL: "wss://tu-backend.railway.app/ws",
    HF_SPACE_BASE_URL: "https://raiden456-slut.hf.space",
    HF_SPACE_URL: "https://raiden456-slut.hf.space/run/predict?fn_index=0",
    RAILWAY_AI_BACKUP_URL: "https://tu-backup-ia.railway.app/api/chat",
    API_KEY: null,
    HEALTH_CHECK_INTERVAL: 30000,
    CIRCUIT_BREAKER_THRESHOLD: 3,
    REQUEST_TIMEOUT: 5000,
};

const AURA_HEALTH = {
    railway: { status: "unknown", lastCheck: null, failures: 0 },
    hfSpace: { status: "unknown", lastCheck: null, failures: 0 },
};

class CircuitBreaker {
    constructor(threshold = 3, timeout = 5000) {
        this.threshold = threshold;
        this.timeout = timeout;
        this.failures = 0;
        this.state = "CLOSED";
        this.lastFailure = null;
    }

    async execute(fn, fallback = null) {
        if (this.state === "OPEN") {
            if (Date.now() - this.lastFailure > this.timeout * 10) {
                this.state = "HALF-OPEN";
            } else {
                if (fallback) return await fallback();
                throw new Error("Circuit breaker OPEN");
            }
        }

        try {
            const result = await Promise.race([
                fn(),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error("Timeout")), this.timeout),
                ),
            ]);
            this.onSuccess();
            return result;
        } catch (error) {
            this.onFailure();
            if (fallback && this.state === "OPEN") {
                return await fallback();
            }
            throw error;
        }
    }

    onSuccess() {
        this.failures = 0;
        this.state = "CLOSED";
    }

    onFailure() {
        this.failures++;
        this.lastFailure = Date.now();
        if (this.failures >= this.threshold) {
            this.state = "OPEN";
        }
    }

    reset() {
        this.failures = 0;
        this.state = "CLOSED";
        this.lastFailure = null;
    }
}

const hfCircuit = new CircuitBreaker(
    AURA_CONFIG.CIRCUIT_BREAKER_THRESHOLD,
    AURA_CONFIG.REQUEST_TIMEOUT,
);

async function fetchAI(message, history = [], systemPrompt = "", temperature = 0.7, maxTokens = 2048) {
    return await hfCircuit.execute(
        async () => {
            const response = await fetch(AURA_CONFIG.HF_SPACE_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(AURA_CONFIG.API_KEY && { Authorization: `Bearer ${AURA_CONFIG.API_KEY}` }),
                },
                body: JSON.stringify({
                    data: [message, history, systemPrompt, temperature, maxTokens],
                }),
                mode: "cors",
            });

            if (!response.ok) throw new Error(`HF ${response.status}`);
            const result = await response.json();
            return result.data?.[0] || "Sin respuesta";
        },
        async () => {
            const response = await fetch(AURA_CONFIG.RAILWAY_AI_BACKUP_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    data: [message, history, systemPrompt, temperature, maxTokens],
                }),
                mode: "cors",
            });

            if (!response.ok) throw new Error(`Railway ${response.status}`);
            return await response.json();
        },
    );
}

async function checkEndpoint(name, url) {
    try {
        const response = await fetch(url, { method: "GET", mode: "cors" });
        AURA_HEALTH[name].status = response.ok ? "up" : "degraded";
        AURA_HEALTH[name].failures = response.ok ? 0 : AURA_HEALTH[name].failures + 1;
    } catch {
        AURA_HEALTH[name].status = "down";
        AURA_HEALTH[name].failures++;
    }
    AURA_HEALTH[name].lastCheck = new Date().toISOString();
}

async function updateSystemStatus() {
    await checkEndpoint("railway", AURA_CONFIG.RAILWAY_WS_URL.replace("/ws", "/health"));
    await checkEndpoint("hfSpace", AURA_CONFIG.HF_SPACE_BASE_URL);

    const railEl = document.getElementById("railway-status");
    const hfEl = document.getElementById("hf-space-status");

    if (railEl) {
        railEl.className = `status-dot ${AURA_HEALTH.railway.status}`;
        railEl.title = `Railway: ${AURA_HEALTH.railway.status} (${AURA_HEALTH.railway.lastCheck || "never"})`;
    }

    if (hfEl) {
        hfEl.className = `status-dot ${AURA_HEALTH.hfSpace.status}`;
        hfEl.title = `HF Space: ${AURA_HEALTH.hfSpace.status} (${AURA_HEALTH.hfSpace.lastCheck || "never"})`;
    }
}

function startHealthMonitor() {
    updateSystemStatus();
    setInterval(updateSystemStatus, AURA_CONFIG.HEALTH_CHECK_INTERVAL);
}

window.AURA = {
    CONFIG: AURA_CONFIG,
    HEALTH: AURA_HEALTH,
    fetchAI,
    updateSystemStatus,
    startHealthMonitor,
    CircuitBreaker,
};
