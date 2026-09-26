/**
 * Módulo para manejar notificaciones en segundo plano.
 */

class BackgroundNotifications {
    constructor() {
        this.token = localStorage.getItem('aura_jwt_token');
        this.notificationChannelId = 'aura_urgent_notifications';
        this.socket = null;
        this.isInitialized = false;
    }

    /**
     * Inicializa el plugin de notificaciones.
     */
    async init() {
        if (this.isInitialized) return;

        try {
            // Verificar si el plugin está disponible
            if (!window.Plugins || !window.Plugins.LocalNotifications) {
                console.error('Plugin de notificaciones no disponible');
                return;
            }

            // Crear canal de notificaciones
            await this.createNotificationChannel();

            // Conectar al WebSocket para escuchar eventos
            this.connectWebSocket();

            this.isInitialized = true;
            console.log('Notificaciones en segundo plano inicializadas');
        } catch (error) {
            console.error('Error al inicializar notificaciones:', error);
        }
    }

    /**
     * Crea un canal de notificaciones en Android.
     */
    async createNotificationChannel() {
        try {
            await window.Plugins.LocalNotifications.registerNotificationChannel({
                id: this.notificationChannelId,
                name: 'Notificaciones Urgentes de AURA',
                description: 'Notificaciones importantes de tareas completadas o alertas urgentes',
                importance: 4, // Importancia alta
                sound: 'notification_sound',
                vibration: [0, 250, 250, 250],
                ledColor: 0xff0000,
                enableVibration: true,
                enableLights: true,
                bypassDnd: true,
                showBadge: true,
                lockscreenVisibility: 'public'
            });
        } catch (error) {
            console.error('Error al crear canal de notificaciones:', error);
        }
    }

    /**
     * Conecta al servidor WebSocket para escuchar eventos.
     */
    connectWebSocket() {
        if (this.socket) {
            this.socket.close();
        }

        const wsUrl = 'ws://localhost:8765';
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('Conectado al servidor WebSocket para notificaciones');
        };

        this.socket.onmessage = async (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.eventType === 'ALERTA_URGENTE' || data.eventType === 'TAREA_COMPLETADA') {
                    await this.showUrgentNotification(data);
                }
            } catch (error) {
                console.error('Error al procesar mensaje de notificación:', error);
            }
        };

        this.socket.onclose = () => {
            console.log('Desconectado del servidor WebSocket para notificaciones');
            // Reintentar conexión después de 5 segundos
            setTimeout(() => this.connectWebSocket(), 5000);
        };

        this.socket.onerror = (error) => {
            console.error('Error en WebSocket para notificaciones:', error);
        };
    }

    /**
     * Muestra una notificación urgente.
     */
    async showUrgentNotification(data) {
        try {
            const title = data.title || 'Alerta de AURA';
            const body = data.body || 'Se ha recibido una alerta urgente';

            await window.Plugins.LocalNotifications.schedule({
                notifications: [{
                    title: title,
                    body: body,
                    id: Date.now(),
                    channelId: this.notificationChannelId,
                    sound: 'notification_sound',
                    vibration: [0, 250, 250, 250],
                    data: data,
                    foreground: true,
                    extra: {
                        priority: 'high',
                        importance: 'high'
                    }
                }]
            });

            console.log('Notificación urgente mostrada:', title);
        } catch (error) {
            console.error('Error al mostrar notificación:', error);
        }
    }

    /**
     * Envía un evento de prueba para notificaciones.
     */
    async sendTestNotification() {
        try {
            const testData = {
                eventType: 'ALERTA_URGENTE',
                title: 'Prueba de Notificación',
                body: 'Esta es una notificación de prueba desde AURA',
                timestamp: new Date().toISOString()
            };

            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify(testData));
            } else {
                console.log('WebSocket no conectado. Enviando notificación directamente...');
                await this.showUrgentNotification(testData);
            }
        } catch (error) {
            console.error('Error al enviar notificación de prueba:', error);
        }
    }
}

// Inicializar notificaciones al cargar la página
document.addEventListener('DOMContentLoaded', async () => {
    const backgroundNotifications = new BackgroundNotifications();
    await backgroundNotifications.init();

    // Exponer la API para pruebas
    window.AURA_BackgroundNotifications = backgroundNotifications;
});