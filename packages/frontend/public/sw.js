const CACHE_NAME = "ame-mobile-v1";
const ASSETS_TO_CACHE = ["/", "/ame", "/manifest.json", "/offline.html"];

// Instalación - cachear assets iniciales
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[SW] Caching initial assets");
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.log("[SW] Some assets failed to cache:", err);
      });
    }),
  );
  self.skipWaiting();
});

// Activación - limpiar caches viejos
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      );
    }),
  );
  self.clients.claim();
});

// Estrategia: Network First con fallback a cache
self.addEventListener("fetch", (event) => {
  // Solo requests GET
  if (event.request.method !== "GET") return;

  // Para la API, siempre network primero
  if (event.request.url.includes("/api/")) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Para assets estáticos, cache first
  if (
    event.request.url.match(/\.(js|css|png|jpg|svg|ico|json)$/) ||
    event.request.url.includes("/_next/")
  ) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // Para navegación, network first
  event.respondWith(networkFirst(event.request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const clone = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
    }
    return response;
  } catch {
    return caches.match("/offline.html");
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const clone = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;

    // Si es navegación, devolver offline
    if (request.mode === "navigate") {
      return caches.match("/offline.html");
    }

    return new Response(
      JSON.stringify({ error: "offline", message: "Sin conexión" }),
      { headers: { "Content-Type": "application/json" } },
    );
  }
}
