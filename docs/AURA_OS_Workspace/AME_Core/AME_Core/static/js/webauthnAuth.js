/**
 * webauthnAuth.js — Autenticación biométrica vía WebAuthn API (PWA)
 * Reemplaza la dependencia de Capacitor nativo por la API estándar del navegador.
 * Soporta huella dactilar / FaceID / PIN del dispositivo sin plugins.
 */
import { getTokenSecurely, removeTokenSecurely, storeTokenSecurely } from "./secureStorage.js";
const API = window.location.origin;
const AUTH_ENDPOINT = "/api/auth/webauthn/register";
const LOGIN_ENDPOINT = "/api/auth/webauthn/verify";
const VALIDATE_ENDPOINT = "/api/auth/validate";
const SESSION_TOKEN_KEY = "aura_session_token";

let _fetchPatched = false;

function patchFetch(token) {
    if (_fetchPatched) return;
    _fetchPatched = true;
    const orig = window.fetch;
    window.fetch = function (url, opts = {}) {
        if (typeof url === "string" && !url.includes("/api/auth/")) {
            opts.headers = { ...opts.headers, Authorization: `Bearer ${token}` };
        }
        return orig(url, opts);
    };
}

function toast(msg, color = "#ff4444") {
    const el = document.createElement("div");
    el.style.cssText = `position:fixed;bottom:24px;right:24px;z-index:9999;background:${color};color:#fff;padding:12px 20px;border-radius:12px;font-size:14px;max-width:320px;box-shadow:0 4px 24px rgba(0,0,0,0.4);animation:slideIn .3s ease;`;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => {
        el.style.opacity = "0";
        el.style.transition = "opacity .3s";
        setTimeout(() => el.remove(), 300);
    }, 4000);
}

// ─── WebAuthn: Registrar credencial en el dispositivo ─────────────────
async function registerWebAuthn() {
    try {
        const resp = await fetch(`${API}/api/auth/webauthn/begin-register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: "architect" }),
        });
        if (!resp.ok) throw new Error("Falló al iniciar registro WebAuthn");
        const options = await resp.json();
        options.challenge = Uint8Array.from(atob(options.challenge), (c) => c.charCodeAt(0));
        options.user.id = Uint8Array.from(atob(options.user.id), (c) => c.charCodeAt(0));
        if (options.excludeCredentials)
            options.excludeCredentials = options.excludeCredentials.map((c) => ({
                ...c,
                id: Uint8Array.from(atob(c.id), (x) => x.charCodeAt(0)),
            }));
        const credential = await navigator.credentials.create({ publicKey: options });
        if (!credential) throw new Error("Registro cancelado por el usuario");
        const payload = {
            id: credential.id,
            rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
            type: credential.type,
            response: {
                clientDataJSON: btoa(
                    String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON)),
                ),
                attestationObject: btoa(
                    String.fromCharCode(...new Uint8Array(credential.response.attestationObject)),
                ),
            },
        };
        const finish = await fetch(`${API}${AUTH_ENDPOINT}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!finish.ok) throw new Error("Falló al completar registro WebAuthn");
        return await finish.json();
    } catch (e) {
        if (e.name === "NotAllowedError") throw new Error("Autenticación cancelada");
        if (e.name === "SecurityError")
            throw new Error("El contexto no es seguro (HTTPS requerido)");
        throw e;
    }
}

// ─── WebAuthn: Verificar / hacer login ───────────────────────────────
async function verifyWebAuthn() {
    try {
        const resp = await fetch(`${API}/api/auth/webauthn/begin-verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: "architect" }),
        });
        if (!resp.ok) throw new Error("Falló al iniciar verificación WebAuthn");
        const options = await resp.json();
        options.challenge = Uint8Array.from(atob(options.challenge), (c) => c.charCodeAt(0));
        if (options.allowCredentials)
            options.allowCredentials = options.allowCredentials.map((c) => ({
                ...c,
                id: Uint8Array.from(atob(c.id), (x) => x.charCodeAt(0)),
            }));
        const assertion = await navigator.credentials.get({ publicKey: options });
        if (!assertion) throw new Error("Verificación cancelada por el usuario");
        const payload = {
            id: assertion.id,
            rawId: btoa(String.fromCharCode(...new Uint8Array(assertion.rawId))),
            type: assertion.type,
            response: {
                clientDataJSON: btoa(
                    String.fromCharCode(...new Uint8Array(assertion.response.clientDataJSON)),
                ),
                authenticatorData: btoa(
                    String.fromCharCode(...new Uint8Array(assertion.response.authenticatorData)),
                ),
                signature: btoa(
                    String.fromCharCode(...new Uint8Array(assertion.response.signature)),
                ),
                userHandle: assertion.response.userHandle
                    ? btoa(String.fromCharCode(...new Uint8Array(assertion.response.userHandle)))
                    : null,
            },
        };
        const finish = await fetch(`${API}${LOGIN_ENDPOINT}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!finish.ok) throw new Error("Firma biométrica no válida");
        const data = await finish.json();
        return data.token;
    } catch (e) {
        if (e.name === "NotAllowedError") throw new Error("Autenticación cancelada");
        throw e;
    }
}

// ─── Flujo de autenticación principal ────────────────────────────────
async function authenticate() {
    const stored = await getTokenSecurely();
    if (stored) {
        try {
            const r = await fetch(`${API}${VALIDATE_ENDPOINT}`, {
                method: "POST",
                headers: { Authorization: `Bearer ${stored}`, "Content-Type": "application/json" },
            });
            if (r.ok) {
                patchFetch(stored);
                return stored;
            }
        } catch {
            /* ignora error de red, intenta registro */
        }
        await removeTokenSecurely();
    }
    if (!navigator.credentials || !navigator.credentials.create) {
        // Fallback a PIN estático si no hay WebAuthn
        const pin = prompt("🔐 Ingrese PIN de acceso a AURA:");
        if (pin === "AURA2024!") {
            const r = await fetch(`${API}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pin }),
            });
            if (r.ok) {
                const d = await r.json();
                await storeTokenSecurely(d.token);
                patchFetch(d.token);
                return d.token;
            }
        }
        throw new Error("PIN incorrecto o WebAuthn no disponible");
    }
    try {
        const token = await verifyWebAuthn();
        await storeTokenSecurely(token);
        patchFetch(token);
        return token;
    } catch (e) {
        if (e.message.includes("no encontrada") || e.message.includes("not found")) {
            toast("Registrando credencial biométrica...", "#2196f3");
            await registerWebAuthn();
            const token = await verifyWebAuthn();
            await storeTokenSecurely(token);
            patchFetch(token);
            return token;
        }
        throw e;
    }
}

// ─── Inicialización ──────────────────────────────────────────────────
async function initAuth() {
    try {
        const token = await authenticate();
        toast("✅ Autenticación exitosa", "#4caf50");
        return token;
    } catch (e) {
        console.error("[WebAuthn] Error:", e);
        toast(`❌ ${e.message}`);
        window.location.href = "/lockscreen.html";
        return null;
    }
}

export { authenticate, initAuth, patchFetch };
