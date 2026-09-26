/*
 * Service Worker para AURA - Optimizado para PWA mobile
 * Cache-first para assets estaticos, network-first para APIs
 * SPA routing: navegacion entre paginas sin recarga
 */

"use strict";

const CACHE_NAME = "aura-pwa-v1";
const API_CACHE_NAME = "aura-api-v1";

const CRITICAL_ASSETS = [
    "/",
    "/index.html",
    "/dashboard.html",
    "/static/css/style.css",
    "/static/css/tactical_dashboard.css",
    "/static/css/decision_core_styles.css",
    "/static/js/voice_command.js",
    "/static/js/tactical_dashboard.js",
    "/static/js/physics_ui.js",
    "/static/js/action_queue_manager.js",
    "/static/js/decision_core_integration.js",
    "/static/images/aura-icon-192x192.png",
    "/static/images/aura-icon-512x512.png",
    "/manifest.json",
    "/offline.html",
];

const NAVIGATION_URLS = [
    "/",
    "/index.html",
    "/dashboard.html",
    "/blue",
    "/api/radar",
    "/api/tasks",
    "/api/status",
];

// ============ INSTALL ============
self.addEventListener("install", (event) => {
    console.log("[SW] Instalando AURA PWA v1");
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(CRITICAL_ASSETS);
            })
            .then(() => self.skipWaiting()),
    );
});

// ============ ACTIVATE ============
self.addEventListener("activate", (event) => {
    console.log("[SW] Activado - Limpiando caches antiguos");
    event.waitUntil(
        caches
            .keys()
            .then((keys) => {
                return Promise.all(
                    keys
                        .filter((k) => k !== CACHE_NAME && k !== API_CACHE_NAME)
                        .map((k) => caches.delete(k)),
                );
            })
            .then(() => self.clients.claim()),
    );
});

// ============ FETCH (SPA + Cache) ============
self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Solo HTTP(S)
    if (url.protocol !== "http:" && url.protocol !== "https:") return;

    // ============ SPA ROUTING ============
    // Si es navegacion (documento HTML) y no es un asset estatico,
    // interceptar para servir index.html (navegacion SPA sin recarga)
    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(() =>
                caches.match("/offline.html").then((r) => r || caches.match("/")),
            ),
        );
        return;
    }

    // ============ API REQUESTS (Network First) ============
    if (url.pathname.startsWith("/api/")) {
        event.respondWith(networkFirst(request, API_CACHE_NAME));
        return;
    }

    // ============ STATIC ASSETS (Cache First) ============
    event.respondWith(cacheFirst(request));
});

// ============ STRATEGIES ============

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        // Si es una navegacion fallback, servir offline
        if (request.mode === "navigate") {
            return caches.match("/offline.html");
        }
        throw err;
    }
}

async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response(JSON.stringify({ status: "offline", error: "Sin conexion" }), {
            headers: { "Content-Type": "application/json" },
        });
    }
}

// ============ PUSH NOTIFICATIONS ============
self.addEventListener("push", (event) => {
    if (!event.data) return;
    try {
        const data = event.data.json();
        self.registration.showNotification(data.title || "AURA System", {
            body: data.body || "Notificacion del sistema",
            icon: "/static/images/aura-icon-192x192.png",
            badge: "/static/images/aura-icon-192x192.png",
            data: { url: data.url || "/" },
            actions: [
                { action: "view", title: "Abrir" },
                { action: "close", title: "Cerrar" },
            ],
        });
    } catch (e) {
        console.error("[SW] Error en push:", e);
    }
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = event.notification.data?.url || "/";
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
            if (clients.length > 0) {
                return clients[0].navigate(url).then(() => clients[0].focus());
            }
            return clients.openWindow(url);
        }),
    );
});

// ============ SYNC ============
self.addEventListener("sync", (event) => {
    if (event.tag === "sync-aura") {
        console.log("[SW] Sincronizacion de fondo");
    }
});
