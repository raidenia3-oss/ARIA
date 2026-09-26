/*
Hologram Gestures para AURA Tactical Dashboard.
Gestiona la interacción con gestos detectados por MediaPipe.
*/

// Configuración global
const gestureManager = {
    socket: null,
    handCursor: null,
    gestureOverlay: null,
    isConnected: false,

    // Inicializar el gestor de gestos
    init: function() {
        this.setupSocketConnection();
        this.createGestureOverlay();
    },

    // Configurar conexión Socket.IO
    setupSocketConnection: function() {
        if (typeof io !== 'undefined') {
            this.socket = io({
                transports: ['websocket'],
                reconnection: true,
                reconnectionAttempts: Infinity,
                reconnectionDelay: 1000,
                timeout: 20000,
                pingInterval: 10000,
                pingTimeout: 5000
            });

            this.socket.on('connect', () => {
                console.log('🔗 Conectado al servidor de gestos');
                this.isConnected = true;
            });

            this.socket.on('disconnect', () => {
                console.log('🔘 Desconectado del servidor de gestos');
                this.isConnected = false;
            });

            this.socket.on('gesture_detected', (data) => {
                console.log('🤚 Gesto detectado:', data.message);
                this.handleGesture(data.gesture);
            });

            this.socket.on('gesture_position', (data) => {
                this.updateHandCursor(data.x, data.y);
            });
        }
    },

    // Crear overlay para el cursor de mano
    createGestureOverlay: function() {
        // Crear elemento para el cursor de mano
        this.handCursor = document.createElement('div');
        this.handCursor.className = 'hand-cursor';
        this.handCursor.style.display = 'none';
        document.body.appendChild(this.handCursor);

        // Crear overlay para mostrar gestos detectados
        this.gestureOverlay = document.createElement('div');
        this.gestureOverlay.className = 'gesture-overlay';
        this.gestureOverlay.style.display = 'none';
        document.body.appendChild(this.gestureOverlay);
    },

    // Actualizar posición del cursor de mano
    updateHandCursor: function(x, y) {
        if (this.handCursor) {
            this.handCursor.style.left = `${x}px`;
            this.handCursor.style.top = `${y}px`;
            this.handCursor.style.display = 'block';
        }
    },

    // Ocultar cursor de mano
    hideHandCursor: function() {
        if (this.handCursor) {
            this.handCursor.style.display = 'none';
        }
    },

    // Manejar gestos detectados
    handleGesture: function(gesture) {
        switch (gesture) {
            case 'fist':
                this.closeMenu();
                break;
            case 'point':
                this.selectNode();
                break;
            default:
                break;
        }
    },

    // Cerrar menú con gesto de puño
    closeMenu: function() {
        console.log('👊 Menú cerrado con gesto de puño');
        if (document.querySelector('.sidebar')) {
            document.querySelector('.sidebar').style.display = 'none';
        }
    },

    // Seleccionar nodo con gesto de dedo señalando
    selectNode: function() {
        console.log('👆 Nodo seleccionado con gesto de dedo señalando');
        // Aquí podrías implementar lógica para seleccionar nodos 3D
        // Ejemplo: emitir evento para seleccionar el nodo más cercano al cursor
        if (typeof tacticalDashboard !== 'undefined' && tacticalDashboard.threatRadar) {
            tacticalDashboard.threatRadar.data.critical += 1;
            tacticalDashboard.threatRadar.drawRadar();
        }
    },

    // Mostrar mensaje de gesto detectado
    showGestureMessage: function(message) {
        if (this.gestureOverlay) {
            this.gestureOverlay.textContent = message;
            this.gestureOverlay.style.display = 'block';
            setTimeout(() => {
                this.gestureOverlay.style.display = 'none';
            }, 2000);
        }
    }
};

// Inicializar el gestor de gestos cuando la página esté cargada
document.addEventListener('DOMContentLoaded', function() {
    gestureManager.init();

    // Conectar al servidor de gestos
    if (gestureManager.socket) {
        gestureManager.socket.connect('ws://localhost:5003');
    }
});