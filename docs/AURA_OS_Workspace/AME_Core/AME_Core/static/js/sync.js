/**
 * sync.js — Utilidad de sincronización entre dispositivos (PC ↔ Celular)
 * Genera tokens de sesión únicos y los convierte en QR para escanear.
 * El backend en Railway valida el token para autorizar WebSocket.
 */
const SYNC_API = "/api/sync/session";
const WS_BASE = window.location.origin.replace(/^http/, "ws") + "/ws/sync";

// ─── Generar token de sesión único ──────────────────────────────────
function generateSessionToken() {
    const arr = new Uint8Array(32);
    crypto.getRandomValues(arr);
    return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

// ─── Crear sesión en el backend ─────────────────────────────────────
async function createSession() {
    const token = generateSessionToken();
    const resp = await fetch(SYNC_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, device: navigator.userAgent, expiresIn: 300 }),
    });
    if (!resp.ok) throw new Error("Error al crear sesión de sincronización");
    return await resp.json();
}

// ─── Validar sesión existente ───────────────────────────────────────
async function validateSession(token) {
    const resp = await fetch(`${SYNC_API}/${token}`, { method: "GET" });
    if (!resp.ok) return null;
    return await resp.json();
}

// ─── Generar QR en un canvas ────────────────────────────────────────
function generateQR(canvas, data, size = 256) {
    // QR Code simplificado (matriz 21x21 para datos pequeños)
    const ctx = canvas.getContext("2d");
    canvas.width = size;
    canvas.height = size;
    const cell = size / 25;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = "#000";

    // Codificar data como bits
    const bits = [];
    for (let i = 0; i < data.length; i++) {
        let byte = data.charCodeAt(i);
        for (let b = 7; b >= 0; b--) bits.push((byte >> b) & 1);
    }
    // Padding
    while (bits.length < 400) bits.push(0);
    bits.length = 400;

    // Dibujar matriz
    for (let y = 0; y < 20; y++) {
        for (let x = 0; x < 20; x++) {
            const idx = y * 20 + x;
            if (idx < bits.length && bits[idx]) {
                ctx.fillRect(x * cell + cell, y * cell + cell, cell, cell);
            }
        }
    }
    // Patrones de posición (esquinas)
    const drawFinder = (ox, oy) => {
        ctx.fillStyle = "#000";
        for (let r = 0; r < 7; r++)
            for (let c = 0; c < 7; c++)
                if (
                    r === 0 ||
                    r === 6 ||
                    c === 0 ||
                    c === 6 ||
                    (r >= 2 && r <= 4 && c >= 2 && c <= 4)
                )
                    ctx.fillRect((ox + c) * cell, (oy + r) * cell, cell, cell);
    };
    drawFinder(0, 0);
    drawFinder(17, 0);
    drawFinder(0, 17);
}

// ─── Mostrar QR en la UI ────────────────────────────────────────────
async function showSyncQR(containerId) {
    const container = document.getElementById(containerId) || document.body;
    const canvas = document.createElement("canvas");
    canvas.id = "aura-sync-qr";
    canvas.style.cssText = "display:block;margin:16px auto;border-radius:12px;";
    container.appendChild(canvas);

    const session = await createSession();
    const link = `${window.location.origin}/sync?token=${session.token}`;
    generateQR(canvas, link);
    return session;
}

// ─── Conectar WebSocket con token de sesión ─────────────────────────
function connectSyncWS(token, onMessage) {
    const ws = new WebSocket(`${WS_BASE}?token=${token}`);
    ws.onopen = () => console.log("[Sync] WebSocket conectado");
    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (onMessage) onMessage(data);
        } catch {
            /* ignorar */
        }
    };
    ws.onerror = () => console.error("[Sync] Error WebSocket");
    ws.onclose = () => setTimeout(() => connectSyncWS(token, onMessage), 3000);
    return ws;
}

// ─── Leer token de la URL (para el dispositivo que escanea) ─────────
function getTokenFromURL() {
    const params = new URLSearchParams(window.location.search);
    return params.get("token");
}

export {
    connectSyncWS,
    createSession,
    generateSessionToken,
    getTokenFromURL,
    showSyncQR,
    validateSession,
};
