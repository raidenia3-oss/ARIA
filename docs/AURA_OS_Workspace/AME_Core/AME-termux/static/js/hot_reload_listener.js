/*
 * hot_reload_listener.js - Listener de WebSocket para Hot-Reload en AME.
 * Este script se conecta al servidor de Hot-Reload de AURA y recarga la página
 * cuando detecta cambios en los archivos del frontend.
 */

// Configuración global
const HOT_RELOAD_WS_URL = "ws://localhost:8080";
let hotReloadWebSocket = null;
let isConnected = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 2000; // 2 segundos

// DOM Elements
const connectionStatusElement = document.createElement('div');
connectionStatusElement.id = 'hot-reload-status';
connectionStatusElement.style.position = 'fixed';
connectionStatusElement.style.bottom = '10px';
connectionStatusElement.style.right = '10px';
connectionStatusElement.style.padding = '8px 12px';
connectionStatusElement.style.backgroundColor = '#4CAF50';
connectionStatusElement.style.color = 'white';
connectionStatusElement.style.borderRadius = '4px';
connectionStatusElement.style.fontSize = '12px';
connectionStatusElement.style.zIndex = '9999';
connectionStatusElement.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
connectionStatusElement.textContent = 'Desconectado del Hot-Reload';
document.body.appendChild(connectionStatusElement);

// Función para conectar al servidor WebSocket
function connectWebSocket() {
    if (isConnected) {
        return;
    }

    try {
        hotReloadWebSocket = new WebSocket(HOT_RELOAD_WS_URL);

        hotReloadWebSocket.onopen = function() {
            isConnected = true;
            reconnectAttempts = 0;
            connectionStatusElement.textContent = 'Conectado al Hot-Reload';
            connectionStatusElement.style.backgroundColor = '#4CAF50';
            console.log('Conectado al servidor de Hot-Reload');
        };

        hotReloadWebSocket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                handleHotReloadEvent(data);
            } catch (e) {
                console.error('Error al procesar mensaje de Hot-Reload:', e);
            }
        };

        hotReloadWebSocket.onclose = function() {
            isConnected = false;
            connectionStatusElement.textContent = 'Desconectado del Hot-Reload';
            connectionStatusElement.style.backgroundColor = '#F44336';
            console.log('Desconectado del servidor de Hot-Reload');

            // Intentar reconectar
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`Intentando reconectar (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                setTimeout(connectWebSocket, RECONNECT_DELAY);
            } else {
                console.error('Máximo de intentos de reconexión alcanzado.');
                connectionStatusElement.textContent = 'Error: Máximo de reconexiones';
                connectionStatusElement.style.backgroundColor = '#FF9800';
            }
        };

        hotReloadWebSocket.onerror = function(error) {
            console.error('Error en la conexión WebSocket:', error);
            isConnected = false;
            connectionStatusElement.textContent = 'Error en la conexión';
            connectionStatusElement.style.backgroundColor = '#F44336';
        };

    } catch (e) {
        console.error('Error al crear conexión WebSocket:', e);
        isConnected = false;
        connectionStatusElement.textContent = 'Error: No se pudo conectar';
        connectionStatusElement.style.backgroundColor = '#F44336';
    }
}

// Manejar eventos de Hot-Reload
function handleHotReloadEvent(data) {
    if (data.type === 'hot_reload') {
        console.log('Evento de Hot-Reload recibido:', data.message);

        // Mostrar notificación temporal
        const notification = document.createElement('div');
        notification.style.position = 'fixed';
        notification.style.bottom = '60px';
        notification.style.right = '10px';
        notification.style.padding = '12px 20px';
        notification.style.backgroundColor = '#2196F3';
        notification.style.color = 'white';
        notification.style.borderRadius = '4px';
        notification.style.fontSize = '14px';
        notification.style.zIndex = '9998';
        notification.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        notification.style.animation = 'fadeOut 3s forwards';
        notification.textContent = `🔄 Hot-Reload: ${data.message}`;

        document.body.appendChild(notification);

        // Definir animación CSS
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeOut {
                from { opacity: 1; transform: translateY(0); }
                to { opacity: 0; transform: translateY(20px); }
            }
        `;
        document.head.appendChild(style);

        // Ejecutar recarga según el tipo de evento
        if (data.action === 'reload' || data.action === 'hard_reload') {
            console.log('Ejecutando recarga de la página...');
            window.location.reload();
        }
    } else if (data.type === 'welcome') {
        console.log('Bienvenido al servidor de Hot-Reload:', data.message);
    }
}

// Inicializar el listener de Hot-Reload
function initHotReloadListener() {
    console.log('Inicializando listener de Hot-Reload...');

    // Conectar al servidor WebSocket
    connectWebSocket();

    // Manejar eventos de la página (antes de recargar)
    window.addEventListener('beforeunload', function() {
        if (hotReloadWebSocket) {
            hotReloadWebSocket.close();
        }
    });
}

// Iniciar el listener cuando el DOM esté cargado
document.addEventListener('DOMContentLoaded', function() {
    initHotReloadListener();

    // Mostrar mensaje de información en la consola
    console.info(
        '%c HOT-RELOAD ACTIVADO ' +
        '✅ Conectado al servidor de Hot-Reload en ws://localhost:8080\n' +
        '🔄 La página se recargará automáticamente al detectar cambios en los archivos del frontend.\n' +
        '📁 Archivos monitoreados: AME_Core/*.{html,js,css,json,ts,tsx}',
        'background: #4CAF50; color: white; padding: 5px; border-radius: 3px; font-weight: bold;'
    );
});