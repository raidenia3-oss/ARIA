const CACHE_NAME = "ame-v1";
const urlsToCache = [
    "/",
    "/index.html",
    "/css/style.css",
    "/css/tactical_dashboard.css",
    "/css/osint_intelligence.css",
    "/js/services.js",
    "/js/biometricAuth.js",
    "/js/telemetry_dashboard.js",
    "/js/action_queue_manager.js",
    "/js/voice_command.js",
    "/js/background_notifications.js",
    "/js/ghost_mode_toggle.js",
    "/js/radar_module.js",
    "/js/sentinel_module.js",
    "/js/osint_intelligence.js",
    "/js/ame_chat.js",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache)));
});

self.addEventListener("fetch", (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => response || fetch(event.request)),
    );
});
