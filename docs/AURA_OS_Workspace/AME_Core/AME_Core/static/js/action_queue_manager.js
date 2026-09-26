/*
Action Queue Manager para AURA Tactical Dashboard
Gestiona la cola de acciones y optimiza la interfaz para dispositivos táctiles.
*/

// Configuración global
const actionQueueManager = {
    // Configuración de la cola de acciones
    queue: [],
    container: document.getElementById('actionQueueContainer'),
    mobileMode: false,

    // Inicializar el gestor de cola
    init: function() {
        this.loadQueue();
        this.setupEventListeners();
        this.detectDevice();
    },

    // Detectar dispositivo móvil y ajustar calidad
    detectDevice: function() {
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        if (isMobile) {
            this.mobileMode = true;
            console.log("Dispositivo móvil detectado. Optimizando interfaz táctil...");
            document.body.classList.add('mobile-device');

            // Ajustar tamaño de botones para táctil
            this.adjustButtonSizes();
        }
    },

    // Ajustar tamaño de botones para dispositivos táctiles
    adjustButtonSizes: function() {
        const approveButtons = document.querySelectorAll('.action-approve');
        const denyButtons = document.querySelectorAll('.action-deny');

        approveButtons.forEach(button => {
            button.style.height = '60px';
            button.style.width = '120px';
            button.style.fontSize = '18px';
            button.style.padding = '10px 20px';
            button.style.borderRadius = '8px';
        });

        denyButtons.forEach(button => {
            button.style.height = '60px';
            button.style.width = '120px';
            button.style.fontSize = '18px';
            button.style.padding = '10px 20px';
            button.style.borderRadius = '8px';
        });

        // Añadir feedback háptico (vibración) al hacer clic
        approveButtons.forEach(button => {
            button.addEventListener('click', () => {
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }
            });
        });

        denyButtons.forEach(button => {
            button.addEventListener('click', () => {
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }
            });
        });
    },

    // Cargar la cola de acciones desde el backend
    loadQueue: function() {
        fetch('/api/action_queue')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    this.queue = data.queue;
                    this.renderQueue();
                }
            })
            .catch(error => {
                console.error('Error cargando la cola de acciones:', error);
            });
    },

    // Renderizar la cola de acciones
    renderQueue: function() {
        if (!this.container) return;

        this.container.innerHTML = '';

        if (this.queue.length === 0) {
            this.container.innerHTML = '<div class="empty-queue">No hay acciones pendientes.</div>';
            return;
        }

        this.queue.forEach(action => {
            const actionElement = document.createElement('div');
            actionElement.className = 'action-item';
            actionElement.innerHTML = `
                <div class="action-header">
                    <h3>${action.title || 'Sin título'}</h3>
                    <span class="action-type">${action.type || 'General'}</span>
                </div>
                <div class="action-content">
                    <p>${action.content || 'Sin contenido'}</p>
                </div>
                <div class="action-meta">
                    <span class="action-date">${action.date || 'Hoy'}</span>
                    <span class="action-author">${action.author || 'Sistema'}</span>
                </div>
                <div class="action-buttons">
                    <button class="action-approve" data-id="${action.id}">APPROVE</button>
                    <button class="action-deny" data-id="${action.id}">DENY</button>
                </div>
            `;
            this.container.appendChild(actionElement);
        });

        // Añadir eventos a los botones
        this.setupActionButtons();
    },

    // Configurar eventos para los botones de acción
    setupActionButtons: function() {
        const approveButtons = document.querySelectorAll('.action-approve');
        const denyButtons = document.querySelectorAll('.action-deny');

        approveButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const actionId = e.target.getAttribute('data-id');
                this.processAction(actionId, 'approve');
            });
        });

        denyButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const actionId = e.target.getAttribute('data-id');
                this.processAction(actionId, 'deny');
            });
        });
    },

    // Procesar una acción (APPROVE o DENY)
    processAction: function(actionId, decision) {
        fetch(`/api/action_queue/${actionId}?decision=${decision}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                this.loadQueue(); // Recargar la cola
                this.showNotification(`Acción ${decision.toUpperCase()}: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error procesando acción:', error);
        });
    },

    // Mostrar notificación en el navegador
    showNotification: function(message) {
        if (!('Notification' in window)) {
            console.log('Notificaciones no soportadas en este navegador.');
            return;
        }

        if (Notification.permission === 'granted') {
            new Notification('AURA Tactical', {
                body: message,
                icon: '/static/images/aura-icon-192x192.png',
                vibrate: [200, 100, 200]
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification('AURA Tactical', {
                        body: message,
                        icon: '/static/images/aura-icon-192x192.png',
                        vibrate: [200, 100, 200]
                    });
                }
            });
        }
    },

    // Configurar eventos para el gestor de cola
    setupEventListeners: function() {
        this.setupHeartbeat(); {
        // Recargar la cola cada 10 segundos
        setInterval(() => {
            this.loadQueue();
        }, 10000);
    },

    // Registrar Service Worker para notificaciones push
    registerServiceWorker: function() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(registration => {
                    console.log('ServiceWorker registrado con éxito:', registration.scope);
                    return registration;
                })
                .then(registration => {
                    // Solicitar permiso para notificaciones push
                    if (!('PushManager' in window)) {
                        console.log('Notificaciones push no soportadas en este navegador.');
                        return;
                    }

                    return registration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: 'YOUR_VAPID_PUBLIC_KEY' // Reemplazar con tu clave VAPID
                    });
                })
                .then(subscription => {
                    console.log('Suscripción a push:', subscription);
                    // Enviar la suscripción al backend para almacenarla
                    this.sendPushSubscription(subscription);
                })
                .catch(error => {
                    console.error('Error al registrar ServiceWorker o suscripción:', error);
                });
        }
    },

    // Enviar suscripción a push al backend
    sendPushSubscription: function(subscription) {
        fetch('/api/register_push_subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                subscription: subscription.toJSON()
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Suscripción enviada al backend:', data);
        })
        .catch(error => {
            console.error('Error enviando suscripción:', error);
        });
    }
};

// Inicializar el gestor de cola cuando la página esté cargada
document.addEventListener('DOMContentLoaded', function() {
    actionQueueManager.init();
    actionQueueManager.registerServiceWorker();
});
