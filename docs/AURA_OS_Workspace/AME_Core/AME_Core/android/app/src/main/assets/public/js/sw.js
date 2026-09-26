/*
 * Service Worker para AURA - Optimizado para redes móviles
 * Maneja notificaciones push, caché offline y recuperación de desconexiones
 */

'use strict';

// Configuración para redes móviles
const MOBILE_CONFIG = {
    cacheName: 'aura-mobile-v1',
    offlineFallbackUrl: '/offline.html',
    offlineQueue: [],
    maxOfflineQueueSize: 50,
    retryInterval: 30000, // 30 segundos para reintentos
    maxRetryAttempts: 5,
    criticalAssets: [
        '/',
        '/index.html',
        '/dashboard.html',
        '/static/css/style.css',
        '/static/css/tactical_dashboard.css',
        '/static/css/decision_core_styles.css',
        '/static/js/voice_command.js',
        '/static/js/tactical_dashboard.js',
        '/static/js/physics_ui.js',
        '/static/js/action_queue_manager.js',
        '/static/js/decision_core_integration.js',
        '/static/images/aura-icon.png',
        '/static/images/aura-badge.png',
        '/static/images/agent-completed.png',
        '/static/images/user-avatar.png',
        '/sw.js',
        '/manifest.json'
    ],
    nonCriticalAssets: [
        '/static/js/threejs-postprocessing.js',
        '/static/js/antigravity_nodes.js',
        '/static/js/blackbox.js',
        '/static/js/hologram_gestures.js',
        '/static/js/immersive_ui_upgrade.js'
    ],
    networkQuality: 'unknown',
    isOffline: false,
    lastOnlineCheck: null
};

// Cache para almacenar archivos estáticos
const CACHE_NAME = MOBILE_CONFIG.cacheName;
const urlsToCache = [
    ...MOBILE_CONFIG.criticalAssets,
    ...MOBILE_CONFIG.nonCriticalAssets
];

// Instalar el Service Worker y cachear archivos
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('🔧 Service Worker: Cacheando archivos críticos para redes móviles');
                return cache.addAll(MOBILE_CONFIG.criticalAssets);
            })
            .then(() => {
                // Cachear assets no críticos en segundo plano
                return caches.open(CACHE_NAME)
                    .then(cache => {
                        return cache.addAll(MOBILE_CONFIG.nonCriticalAssets);
                    });
            })
    );
});

// Evento fetch para manejar solicitudes
self.addEventListener('fetch', event => {
    // Ignorar solicitudes a WebSocket y otros protocolos no HTTP
    if (event.request.protocol !== 'http:' && event.request.protocol !== 'https:') {
        return;
    }

    // Ignorar solicitudes de imágenes, estilos y scripts que ya están en la caché
    if (event.request.destination === 'image' ||
        event.request.destination === 'style' ||
        event.request.destination === 'script' ||
        event.request.destination === 'font') {
        return;
    }

    // Verificar si la solicitud es una API o recurso importante
    const isCriticalRequest = MOBILE_CONFIG.criticalAssets.some(url => event.request.url.includes(url));

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Si hay respuesta en caché, devolverla
                if (response) {
                    return response;
                }

                // Si no hay respuesta en caché y es una solicitud crítica, intentar desde la red
                if (isCriticalRequest) {
                    return fetch(event.request)
                        .then(fetchResponse => {
                            // Clonar la respuesta para cachearla
                            const responseToCache = fetchResponse.clone();

                            // Cachear la respuesta si es exitosa
                            caches.open(CACHE_NAME)
                                .then(cache => {
                                    cache.put(event.request, responseToCache);
                                });

                            return fetchResponse;
                        })
                        .catch(fetchError => {
                            // Si falla la red, servir la página de caída (offline.html)
                            return caches.match(MOBILE_CONFIG.offlineFallbackUrl)
                                .then(fallbackResponse => {
                                    if (fallbackResponse) {
                                        return fallbackResponse;
                                    }

                                    // Si no hay página de caída, mostrar un error
                                    return new Response(`
                                        <!DOCTYPE html>
                                        <html>
                                        <head>
                                            <title>Offline</title>
                                            <style>
                                                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                                                h1 { color: #f44336; }
                                                p { color: #666; }
                                            </style>
                                        </head>
                                        <body>
                                            <h1>📶 Offline</h1>
                                            <p>No hay conexión a internet. Algunos recursos pueden no estar disponibles.</p>
                                            <p>Intenta nuevamente más tarde o conectate a una red WiFi.</p>
                                        </body>
                                        </html>
                                    `, {
                                        headers: { 'Content-Type': 'text/html' }
                                    });
                                });
                        });
                } else {
                    // Para solicitudes no críticas, servir desde caché si está disponible
                    return caches.match(event.request)
                        .then(cachedResponse => {
                            if (cachedResponse) {
                                return cachedResponse;
                            }

                            // Si no hay respuesta en caché, intentar desde la red
                            return fetch(event.request)
                                .then(fetchResponse => {
                                    // Clonar la respuesta para cachearla
                                    const responseToCache = fetchResponse.clone();

                                    // Cachear la respuesta si es exitosa
                                    caches.open(CACHE_NAME)
                                        .then(cache => {
                                            cache.put(event.request, responseToCache);
                                        });

                                    return fetchResponse;
                                })
                                .catch(fetchError => {
                                    // Si falla la red, intentar servir desde caché
                                    return caches.match(event.request);
                                });
                        });
                }
            })
    );
});

// Manejar mensajes del cliente
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        event.waitUntil(
            self.registration.showNotification(event.data.notification.title, event.data.notification.options)
                .then(notification => {
                    console.log('🔔 Notificación mostrada desde Service Worker:', event.data.notification.title);
                    return notification;
                })
                .catch(error => {
                    console.error('❌ Error al mostrar notificación desde Service Worker:', error);
                })
        );
    } else if (event.data && event.data.type === 'ADD_TO_OFFLINE_QUEUE') {
        // Añadir solicitud a la cola offline
        addToOfflineQueue(event.data.request, event.data.options);
    } else if (event.data && event.data.type === 'PROCESS_OFFLINE_QUEUE') {
        // Procesar cola offline cuando regrese la conexión
        processOfflineQueue();
    } else if (event.data && event.data.type === 'CHECK_NETWORK_STATUS') {
        // Verificar estado de la red
        checkNetworkStatus();
    }
});

// Manejar notificaciones push
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        console.log('🔔 Notificación push recibida:', data);

        // Mostrar notificación
        const notificationTitle = data.title || 'AURA Intelligence System';
        const notificationOptions = {
            body: data.body || 'Tienes una notificación nueva',
            icon: data.icon || '/static/images/aura-icon.png',
            badge: data.badge || '/static/images/aura-badge.png',
            data: {
                url: data.url || '/',
                timestamp: Date.now()
            },
            actions: data.actions || [
                { action: 'view', title: 'Ver' },
                { action: 'dismiss', title: 'Descartar' }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(notificationTitle, notificationOptions)
                .then(notification => {
                    console.log('🔔 Notificación push mostrada:', notificationTitle);
                    return notification;
                })
                .catch(error => {
                    console.error('❌ Error al mostrar notificación push:', error);
                })
        );
    }
});

// Manejar clics en notificaciones
self.addEventListener('notificationclick', event => {
    event.notification.close();

    // Obtener la URL de los datos de la notificación
    const urlToOpen = event.notification.data.url || '/';

    // Abrir la URL en una nueva pestaña o ventana
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windowClients => {
            // Si ya hay una ventana abierta, enfocarla
            if (windowClients.length > 0) {
                return windowClients[0].navigate(urlToOpen);
            }

            // Si no hay ventanas abiertas, abrir una nueva
            return clients.open(urlToOpen);
        })
    );
});

// Manejar eventos de sincronización
self.addEventListener('sync', event => {
    if (event.tag === 'sync-offline-queue') {
        console.log('🔄 Evento de sincronización: Procesando cola offline');

        // Procesar la cola offline
        event.waitUntil(
            processOfflineQueue()
                .then(() => {
                    console.log('🔄 Cola offline procesada');
                })
        );
    }
});

// Manejar eventos de activación
self.addEventListener('activate', event => {
    console.log('🚀 Service Worker activado');

    // Eliminar caches antiguos
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('🗑️  Eliminando cache antiguo:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );

    // Verificar estado de la red al activar
    checkNetworkStatus();
});

// Manejar eventos de background fetch
self.addEventListener('backgroundfetchsuccess', event => {
    console.log('📥 Descarga en segundo plano completada:', event.request.url);
});

self.addEventListener('backgroundfetchfailure', event => {
    console.error('❌ Error en descarga en segundo plano:', event.request.url, event.error);

    // Añadir a la cola offline si es una solicitud importante
    if (MOBILE_CONFIG.criticalAssets.some(url => event.request.url.includes(url))) {
        addToOfflineQueue(event.request);
    }
});

self.addEventListener('backgroundfetchabort', event => {
    console.log('🛑 Descarga en segundo plano abortada:', event.request.url);

    // Añadir a la cola offline si es una solicitud importante
    if (MOBILE_CONFIG.criticalAssets.some(url => event.request.url.includes(url))) {
        addToOfflineQueue(event.request);
    }
});

// Manejar eventos de periodic sync
self.addEventListener('periodicsyncsuccess', event => {
    console.log('🔄 Sincronización periódica completada:', event.tag);
});

self.addEventListener('periodicsyncerror', event => {
    console.error('❌ Error en sincronización periódica:', event.tag, event.error);
});

// Funciones para manejar cola offline
let offlineQueue = MOBILE_CONFIG.offlineQueue;

// Añadir solicitud a la cola offline
function addToOfflineQueue(request, options = {}) {
    if (!offlineQueue) {
        offlineQueue = [];
    }

    // Verificar si la solicitud ya está en la cola
    const existingIndex = offlineQueue.findIndex(item => item.request.url === request.url);
    if (existingIndex !== -1) {
        // Actualizar la solicitud existente
        offlineQueue[existingIndex].attempts = (offlineQueue[existingIndex].attempts || 0) + 1;
        offlineQueue[existingIndex].lastAttempt = Date.now();
        console.log(`📥 Solicitud ${request.url} añadida nuevamente a la cola offline (intento ${offlineQueue[existingIndex].attempts})`);
        return;
    }

    // Crear nueva entrada en la cola
    const queueItem = {
        request: request,
        options: options || {},
        attempts: 1,
        lastAttempt: Date.now(),
        timestamp: Date.now()
    };

    // Añadir al inicio de la cola
    offlineQueue.unshift(queueItem);

    // Limitar el tamaño de la cola
    if (offlineQueue.length > MOBILE_CONFIG.maxOfflineQueueSize) {
        offlineQueue = offlineQueue.slice(0, MOBILE_CONFIG.maxOfflineQueueSize);
        console.log(`⚠️  Cola offline limitada a ${MOBILE_CONFIG.maxOfflineQueueSize} elementos`);
    }

    console.log(`📥 Solicitud ${request.url} añadida a la cola offline (intento 1)`);

    // Guardar la cola en el almacenamiento
    saveOfflineQueue();
}

// Procesar cola offline
function processOfflineQueue() {
    return new Promise((resolve) => {
        if (!offlineQueue || offlineQueue.length === 0 || MOBILE_CONFIG.isOffline) {
            console.log('📡 No hay cola offline para procesar o estamos offline');
            resolve();
            return;
        }

        console.log('📡 Procesando cola offline...');

        // Procesar cada elemento de la cola
        offlineQueue.forEach((queueItem, index) => {
            // Verificar si la solicitud es una API de voz
            if (queueItem.request.url.includes('/api/voice-command')) {
                // Para comandos de voz, intentar enviar directamente
                try {
                    const fetchRequest = queueItem.request.clone();
                    fetch(fetchRequest, queueItem.options)
                        .then(response => {
                            if (response.ok) {
                                // Eliminar la solicitud de la cola
                                offlineQueue.splice(index, 1);
                                console.log(`📤 Solicitud de voz ${queueItem.request.url} enviada con éxito desde la cola offline`);
                                saveOfflineQueue();
                            } else {
                                console.log(`⚠️  Error al enviar solicitud de voz ${queueItem.request.url}: ${response.status}`);
                            }
                        })
                        .catch(error => {
                            console.log(`⚠️  Error al enviar solicitud de voz ${queueItem.request.url}:`, error);
                        });
                } catch (error) {
                    console.error('❌ Error al procesar solicitud de voz:', error);
                }
            } else {
                // Para otras solicitudes, intentar enviar y luego eliminar de la cola
                try {
                    const fetchRequest = queueItem.request.clone();
                    fetch(fetchRequest, queueItem.options)
                        .then(response => {
                            if (response.ok) {
                                // Eliminar la solicitud de la cola
                                offlineQueue.splice(index, 1);
                                console.log(`📤 Solicitud ${queueItem.request.url} enviada con éxito desde la cola offline`);
                                saveOfflineQueue();
                            } else {
                                console.log(`⚠️  Error al enviar solicitud ${queueItem.request.url}: ${response.status}`);
                            }
                        })
                        .catch(error => {
                            console.log(`⚠️  Error al enviar solicitud ${queueItem.request.url}:`, error);
                        });
                } catch (error) {
                    console.error('❌ Error al procesar solicitud:', error);
                }
            }
        });

        // Guardar la cola actualizada
        saveOfflineQueue();

        // Programar próximo reintento si hay elementos restantes
        if (offlineQueue.length > 0) {
            console.log(`🔄 ${offlineQueue.length} solicitudes restantes en la cola offline. Reintentando en ${MOBILE_CONFIG.retryInterval / 1000} segundos...`);
            setTimeout(processOfflineQueue, MOBILE_CONFIG.retryInterval);
        } else {
            console.log('📥 Cola offline procesada completamente');
            resolve();
        }
    });
}

// Guardar cola offline en el almacenamiento
function saveOfflineQueue() {
    try {
        // Guardar en el almacenamiento del navegador
        return clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windowClients => {
            if (windowClients.length > 0) {
                return windowClients[0].postMessage({
                    type: 'SAVE_OFFLINE_QUEUE',
                    queue: offlineQueue
                }, '*');
            }
            return Promise.resolve();
        });
    } catch (error) {
        console.error('❌ Error al guardar cola offline:', error);
    }
}

// Cargar cola offline desde el almacenamiento
function loadOfflineQueue() {
    try {
        // Intentar cargar desde el almacenamiento del navegador
        return clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windowClients => {
            if (windowClients.length > 0) {
                return windowClients[0].postMessage({
                    type: 'LOAD_OFFLINE_QUEUE'
                }, '*');
            }
            return Promise.resolve();
        });
    } catch (error) {
        console.error('❌ Error al cargar cola offline:', error);
    }
}

// Verificar estado de la red
function checkNetworkStatus() {
    try {
        const currentTime = Date.now();
        MOBILE_CONFIG.lastOnlineCheck = currentTime;

        // Verificar conexión a internet
        fetch('https://www.google.com', {
            method: 'HEAD',
            cache: 'no-store',
            mode: 'no-cors',
            redirect: 'follow',
            timeout: 3000
        })
        .then(response => {
            if (response.ok || response.status === 0) {
                MOBILE_CONFIG.isOffline = false;
                console.log('📡 Conexión a internet restaurada');

                // Notificar a las ventanas abiertas
                clients.matchAll({
                    type: 'window',
                    includeUncontrolled: true
                }).then(windowClients => {
                    windowClients.forEach(client => {
                        client.postMessage({
                            type: 'NETWORK_ONLINE',
                            timestamp: currentTime
                        }, '*');
                    });
                });

                // Procesar cola offline
                processOfflineQueue();

                // Verificar calidad de la conexión
                checkNetworkQuality();
            } else {
                throw new Error('No conectado a internet');
            }
        })
        .catch(error => {
            MOBILE_CONFIG.isOffline = true;
            console.log('📶 Conexión a internet perdida');

            // Notificar a las ventanas abiertas
            clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            }).then(windowClients => {
                windowClients.forEach(client => {
                    client.postMessage({
                        type: 'NETWORK_OFFLINE',
                        timestamp: currentTime
                    }, '*');
                });
            });
        });

    } catch (error) {
        MOBILE_CONFIG.isOffline = true;
        console.error('❌ Error al verificar estado de la red:', error);
    }
}

// Verificar calidad de la conexión
function checkNetworkQuality() {
    try {
        if (navigator.connection) {
            const connection = navigator.connection;
            MOBILE_CONFIG.networkQuality = connection.effectiveType || 'unknown';

            console.log(`📶 Calidad de conexión: ${MOBILE_CONFIG.networkQuality}`);

            // Notificar a las ventanas abiertas
            clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            }).then(windowClients => {
                windowClients.forEach(client => {
                    client.postMessage({
                        type: 'NETWORK_QUALITY_CHANGED',
                        quality: MOBILE_CONFIG.networkQuality
                    }, '*');
                });
            });

            // Escuchar cambios en la conexión
            connection.addEventListener('change', function() {
                MOBILE_CONFIG.networkQuality = connection.effectiveType || 'unknown';
                console.log(`📶 Calidad de conexión cambiada a: ${MOBILE_CONFIG.networkQuality}`);

                // Notificar a las ventanas abiertas
                clients.matchAll({
                    type: 'window',
                    includeUncontrolled: true
                }).then(windowClients => {
                    windowClients.forEach(client => {
                        client.postMessage({
                            type: 'NETWORK_QUALITY_CHANGED',
                            quality: MOBILE_CONFIG.networkQuality
                        }, '*');
                    });
                });
            });
        }
    } catch (error) {
        console.error('❌ Error al verificar calidad de la conexión:', error);
    }
}

// Función para mostrar notificaciones desde el Service Worker
self.showAuraNotification = function(notificationData) {
    const title = notificationData.title || 'AURA Intelligence System';
    const options = {
        body: notificationData.body || 'Tienes una notificación nueva',
        icon: notificationData.icon || '/static/images/aura-icon.png',
        badge: notificationData.badge || '/static/images/aura-badge.png',
        data: {
            url: notificationData.url || '/',
            timestamp: Date.now()
        },
        actions: notificationData.actions || [
            { action: 'view', title: 'Ver' },
            { action: 'dismiss', title: 'Descartar' }
        ]
    };

    return self.registration.showNotification(title, options);
};

// Función para manejar clics en notificaciones
self.handleNotificationClick = function(event) {
    event.notification.close();

    const urlToOpen = event.notification.data.url || '/';

    return clients.matchAll({
        type: 'window',
        includeUncontrolled: true
    }).then(windowClients => {
        // Si ya hay una ventana abierta, enfocarla
        if (windowClients.length > 0) {
            return windowClients[0].navigate(urlToOpen);
        }

        // Si no hay ventanas abiertas, abrir una nueva
        return clients.open(urlToOpen);
    });
};

// Exportar funciones para uso externo
self.notificationHelper = {
    showNotification: self.showAuraNotification,
    handleNotificationClick: self.handleNotificationClick,
    addToOfflineQueue: addToOfflineQueue,
    processOfflineQueue: processOfflineQueue,
    checkNetworkStatus: checkNetworkStatus
};

// Manejar eventos de activación para cargar cola offline
self.addEventListener('activate', event => {
    console.log('🚀 Service Worker activado. Cargando cola offline...');

    // Cargar cola offline si existe
    loadOfflineQueue();
});

// Manejar eventos de desconexión
self.addEventListener('fetch', event => {
    // Verificar si estamos offline y la solicitud es crítica
    if (MOBILE_CONFIG.isOffline && MOBILE_CONFIG.criticalAssets.some(url => event.request.url.includes(url))) {
        console.log('📶 Solicitud crítica en modo offline. Añadiendo a cola offline:', event.request.url);

        // Añadir a la cola offline
        addToOfflineQueue(event.request, {
            method: event.request.method,
            headers: event.request.headers,
            body: event.request.body ? event.request.body : null
        });

        // Servir respuesta de caché si está disponible
        return caches.match(event.request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    return cachedResponse;
                }

                // Si no hay respuesta en caché, mostrar página de caída
                return caches.match(MOBILE_CONFIG.offlineFallbackUrl)
                    .then(fallbackResponse => {
                        if (fallbackResponse) {
                            return fallbackResponse;
                        }

                        // Si no hay página de caída, mostrar error
                        return new Response(`
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <title>Offline</title>
                                <style>
                                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                                    h1 { color: #f44336; }
                                    p { color: #666; }
                                </style>
                            </head>
                            <body>
                                <h1>📶 Offline</h1>
                                <p>No hay conexión a internet. La solicitud ha sido añadida a la cola offline.</p>
                                <p>Intenta nuevamente más tarde o conectate a una red WiFi.</p>
                            </body>
                            </html>
                        `, {
                            headers: { 'Content-Type': 'text/html' }
                        });
                    });
            });
    }
});

// Manejar eventos de sincronización periódica para procesar cola offline
if ('PeriodicSyncManager' in window) {
    self.addEventListener('periodicsync', event => {
        if (event.tag === 'sync-offline-queue') {
            console.log('🔄 Sincronización periódica: Procesando cola offline');
            event.waitUntil(processOfflineQueue());
        }
    });

    // Registrar sincronización periódica
    self.addEventListener('activate', event => {
        event.waitUntil(
            self.registration.periodicSync.register('sync-offline-queue', {
                minInterval: 60 * 60 * 1000, // 1 hora
                maxInterval: 24 * 60 * 60 * 1000 // 24 horas
            })
        );
    });
}