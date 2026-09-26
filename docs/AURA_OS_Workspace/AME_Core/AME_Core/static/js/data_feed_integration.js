/**
 * data_feed_integration.js - Módulo para integrar el servidor de datos en tiempo real
 * con el frontend de AURA usando WebSockets
 */

// Configuración global para la integración con el servidor de datos
const DATA_FEED_INTEGRATION_CONFIG = {
    shadowCoreUrl: 'https://aura-server-01.vercel.app',
    socketIoPort: 5002,
    reconnectInterval: 5000,  // 5 segundos
    maxReconnectAttempts: 10,
    threatLevels: {
        low: { color: '#4CAF50', severity: 1 },
        medium: { color: '#FFC107', severity: 2 },
        high: { color: '#FF5722', severity: 3 },
        critical: { color: '#F44336', severity: 4 },
        warning: { color: '#FF9800', severity: 2 },
        alert: { color: '#FF5722', severity: 3 },
        info: { color: '#2196F3', severity: 1 }
    },
    nodeMapping: {
        'AURA/Shadow-Core/001-shadow-core-spec.md': ['security', 'threat'],
        'AURA/physics_ui_integration.md': ['security'],
        'AURA/antigravity_nodes.md': ['security', 'osint'],
        'AURA/obsidian_integration.md': ['osint']
    },
    connectionTimeout: 30000,  // 30 segundos
    alertHistoryLimit: 100,
    rooms: {
        global: 'Alerta global para todos los clientes',
        osint: 'Alertas específicas de OSINT',
        security: 'Alertas específicas de seguridad',
        threat: 'Alertas de amenaza crítica'
    }
};

// Variables globales
let socketIoClient = null;
let connected = false;
let reconnectAttempts = 0;
let lastAlertTime = null;
let alertHistory = [];
let historyLock = new (function() {
    this.locked = false;
    this.queue = [];
    this.waiting = 0;

    this.acquire = function(callback) {
        this.waiting++;
        while (this.locked) {
            // Esperar un poco antes de volver a intentar
            setTimeout(() => {}, 0);
        }
        this.locked = true;
        this.waiting--;

        try {
            callback();
        } finally {
            this.release();
        }
    };

    this.release = function() {
        this.locked = false;
        if (this.queue.length > 0) {
            const next = this.queue.shift();
            setTimeout(next, 0);
        }
    };

    this.queueLock = function(callback) {
        this.queue.push(() => {
            this.acquire(callback);
        });
    };
})();

// Función para conectar al servidor de datos
function connectToDataFeed() {
    "use strict";

    console.log("Conectando al servidor de datos en tiempo real...");

    try {
        // Verificar si Socket.IO está disponible
        if (typeof io === 'undefined') {
            console.error("Socket.IO no está disponible. Cargando desde CDN...");
            const script = document.createElement('script');
            script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
            script.onload = function() {
                attemptConnection();
            };
            script.onerror = function() {
                console.error("Error al cargar Socket.IO desde CDN");
                return false;
            };
            document.head.appendChild(script);
            return false;
        } else {
            attemptConnection();
            return true;
        }
    } catch (e) {
        console.error("Error al intentar conectar al servidor de datos:", e);
        return false;
    }
}

function attemptConnection() {
    "use strict";

    try {
        // Crear cliente Socket.IO
        socketIoClient = io(DATA_FEED_INTEGRATION_CONFIG.shadowCoreUrl, {
            transports: ['websocket'],
            path: '/socket.io/',
            query: { 'transport': 'websocket' },
            reconnection: true,
            reconnectionAttempts: DATA_FEED_INTEGRATION_CONFIG.maxReconnectAttempts,
            reconnectionDelay: DATA_FEED_INTEGRATION_CONFIG.reconnectInterval,
            timeout: DATA_FEED_INTEGRATION_CONFIG.connectionTimeout,
            autoConnect: false
        });

        // Registrar eventos
        socketIoClient.on('connect', onConnect);
        socketIoClient.on('disconnect', onDisconnect);
        socketIoClient.on('new_alert', onNewAlert);
        socketIoClient.on('system_message', onSystemMessage);
        socketIoClient.on('config_update', onConfigUpdate);

        // Conectar
        socketIoClient.connect();

        return true;
    } catch (e) {
        console.error("Error al crear cliente Socket.IO:", e);
        return false;
    }
}

// Función para manejar eventos de conexión
function onConnect() {
    "use strict";

    connected = true;
    reconnectAttempts = 0;
    console.log("Conexión establecida con el servidor de datos");

    // Suscribirse a salas importantes
    subscribeToRooms(['global', 'security', 'osint', 'threat']);

    // Notificar al sistema
    notifyConnectionEstablished();
}

// Función para manejar eventos de desconexión
function onDisconnect(reason) {
    "use strict";

    connected = false;
    reconnectAttempts++;

    console.warn(`Desconectado del servidor de datos. Motivo: ${reason}. Reintentos: ${reconnectAttempts}`);

    // Notificar al sistema
    notifyDisconnection();
}

// Función para manejar nuevas alertas
function onNewAlert(data) {
    "use strict";

    try {
        // Procesar la alerta
        const processedAlert = processAlert(data);

        // Guardar en historial
        historyLock.acquire(() => {
            alertHistory.push(processedAlert);
            // Limitar historial a las últimas 100 alertas
            if (alertHistory.length > DATA_FEED_INTEGRATION_CONFIG.alertHistoryLimit) {
                alertHistory = alertHistory.slice(-DATA_FEED_INTEGRATION_CONFIG.alertHistoryLimit);
            }
        });

        // Notificar al sistema principal
        notifyNewAlert(processedAlert);

        // Actualizar tiempo de última alerta
        lastAlertTime = new Date();

        console.log(`Alerta recibida: ${processedAlert.id} - ${processedAlert.severity}`);

    } catch (e) {
        console.error("Error al procesar alerta:", e);
    }
}

// Función para manejar mensajes del sistema
function onSystemMessage(data) {
    "use strict";

    try {
        console.log(`Mensaje del sistema: ${data.message || 'Desconocido'}`);
        notifySystemMessage(data);
    } catch (e) {
        console.error("Error al procesar mensaje del sistema:", e);
    }
}

// Función para manejar actualizaciones de configuración
function onConfigUpdate(data) {
    "use strict";

    try {
        console.log("Configuración actualizada recibida del servidor");
        updateConfigFromServer(data);
        notifyConfigUpdate(data);
    } catch (e) {
        console.error("Error al procesar actualización de configuración:", e);
    }
}

// Función para suscribirse a salas
function subscribeToRooms(rooms) {
    "use strict";

    if (!socketIoClient || !socketIoClient.connected) {
        console.warn("No se puede suscribir a salas: no hay conexión activa");
        return false;
    }

    try {
        for (const room of rooms) {
            if (room in DATA_FEED_INTEGRATION_CONFIG.nodeMapping) {
                // Suscribirse a nodos específicos
                for (const nodeRoom of DATA_FEED_INTEGRATION_CONFIG.nodeMapping[room]) {
                    socketIoClient.emit('subscribe', { room: nodeRoom });
                }
            } else {
                // Suscribirse a sala global
                socketIoClient.emit('subscribe', { room: room });
            }
        }

        console.log(`Suscripto a salas: ${rooms.join(', ')}`);
        return true;
    } catch (e) {
        console.error("Error al suscribirse a salas:", e);
        return false;
    }
}

// Función para procesar una alerta
function processAlert(alertData) {
    "use strict";

    const processed = {
        id: alertData.id || 'unknown',
        timestamp: alertData.timestamp || new Date().toISOString(),
        source: alertData.source || 'unknown',
        type: alertData.type || 'unknown',
        severity: alertData.severity || 'info',
        title: alertData.title || 'Alerta sin título',
        description: alertData.description || '',
        details: alertData.details || [],
        affectedNodes: alertData.affected_nodes || [],
        metadata: alertData.metadata || {},
        color: alertData.color || DATA_FEED_INTEGRATION_CONFIG.threatLevels.info.color,
        processed: new Date().toISOString(),
        threatLevel: DATA_FEED_INTEGRATION_CONFIG.threatLevels[alertData.severity || 'info']?.severity || 1
    };

    // Añadir información adicional
    processed.severityInfo = {
        level: processed.severity,
        color: processed.color,
        description: `Nivel de amenaza: ${processed.severity}`
    };

    // Determinar nodos afectados en el sistema
    processed.systemNodes = [];
    for (const nodePath of processed.affectedNodes) {
        if (nodePath in DATA_FEED_INTEGRATION_CONFIG.nodeMapping) {
            processed.systemNodes.push(...DATA_FEED_INTEGRATION_CONFIG.nodeMapping[nodePath]);
        }
    }

    // Asegurarnos de que no haya duplicados
    processed.systemNodes = [...new Set(processed.systemNodes)];

    return processed;
}

// Función para actualizar configuración desde el servidor
function updateConfigFromServer(serverConfig) {
    "use strict";

    // Actualizar niveles de amenaza
    if ('threat_levels' in serverConfig) {
        DATA_FEED_INTEGRATION_CONFIG.threatLevels = serverConfig.threat_levels;
    }

    // Actualizar mapeo de nodos
    if ('node_mapping' in serverConfig) {
        DATA_FEED_INTEGRATION_CONFIG.nodeMapping = serverConfig.node_mapping;
    }

    console.log("Configuración actualizada desde el servidor");
}

// Función para notificar nuevas alertas al sistema principal
function notifyNewAlert(alert) {
    "use strict";

    try {
        // Notificar al sistema de nodos de conocimiento
        if (window.KnowledgeNodes) {
            if (alert.affectedNodes && alert.affectedNodes.length > 0) {
                alert.affectedNodes.forEach(nodePath => {
                    window.KnowledgeNodes.updateThreatState(nodePath, true);
                });
            }
        }

        // Notificar al panel de control táctico
        if (window.AgentControl) {
            window.AgentControl.handleNewAlert(alert);
        }

        // Emitir evento personalizado
        const event = new CustomEvent('newThreatAlert', {
            detail: alert
        });
        window.dispatchEvent(event);

        console.log(`Notificación enviada al sistema principal: ${alert.id}`);

    } catch (e) {
        console.error("Error al notificar nueva alerta:", e);
    }
}

// Función para notificar desconexión
function notifyDisconnection() {
    "use strict";

    try {
        // Notificar al panel de control táctico
        if (window.AgentControl) {
            window.AgentControl.handleDisconnection();
        }

        // Emitir evento personalizado
        const event = new CustomEvent('dataFeedDisconnected', {
            detail: {
                attempts: reconnectAttempts,
                timestamp: new Date().toISOString()
            }
        });
        window.dispatchEvent(event);

        console.log("Notificación de desconexión enviada al sistema principal");

    } catch (e) {
        console.error("Error al notificar desconexión:", e);
    }
}

// Función para notificar conexión establecida
function notifyConnectionEstablished() {
    "use strict";

    try {
        // Notificar al panel de control táctico
        if (window.AgentControl) {
            window.AgentControl.handleConnectionEstablished();
        }

        // Emitir evento personalizado
        const event = new CustomEvent('dataFeedConnected', {
            detail: {
                timestamp: new Date().toISOString(),
                attempts: reconnectAttempts
            }
        });
        window.dispatchEvent(event);

        console.log("Notificación de conexión establecida enviada al sistema principal");

    } catch (e) {
        console.error("Error al notificar conexión establecida:", e);
    }
}

// Función para notificar mensajes del sistema
function notifySystemMessage(message) {
    "use strict";

    try {
        // Notificar al panel de control táctico
        if (window.AgentControl) {
            window.AgentControl.handleSystemMessage(message);
        }

        // Emitir evento personalizado
        const event = new CustomEvent('systemMessage', {
            detail: message
        });
        window.dispatchEvent(event);

        console.log(`Notificación de mensaje del sistema enviada: ${message.message || ''}`);

    } catch (e) {
        console.error("Error al notificar mensaje del sistema:", e);
    }
}

// Función para notificar actualización de configuración
function notifyConfigUpdate(config) {
    "use strict";

    try {
        // Notificar al panel de control táctico
        if (window.AgentControl) {
            window.AgentControl.handleConfigUpdate(config);
        }

        // Emitir evento personalizado
        const event = new CustomEvent('configUpdated', {
            detail: config
        });
        window.dispatchEvent(event);

        console.log("Notificación de actualización de configuración enviada");

    } catch (e) {
        console.error("Error al notificar actualización de configuración:", e);
    }
}

// Función para manejar el ciclo de reconexión
function handleReconnection() {
    "use strict";

    const reconnectInterval = setInterval(() => {
        if (!connected && reconnectAttempts < DATA_FEED_INTEGRATION_CONFIG.maxReconnectAttempts) {
            console.log(`Intentando reconectar... (Intento ${reconnectAttempts + 1})`);
            if (attemptConnection()) {
                // Si la conexión se restableció, reiniciar contador
                reconnectAttempts = 0;
            } else {
                // Esperar antes de intentar nuevamente
                console.log("Conexión fallida. Reintentando en 5 segundos...");
            }
        } else {
            // Si se agotaron los intentos de reconexión
            if (reconnectAttempts >= DATA_FEED_INTEGRATION_CONFIG.maxReconnectAttempts) {
                console.error("Máximo de intentos de reconexión alcanzado. Deteniendo intentos automáticos.");
                clearInterval(reconnectInterval);
            }
        }
    }, DATA_FEED_INTEGRATION_CONFIG.reconnectInterval);

    // Guardar referencia para poder detener el intervalo
    window.dataFeedReconnectionInterval = reconnectInterval;
}

// Función para obtener el historial de alertas
function getAlertHistory(limit) {
    "use strict";

    if (limit === undefined) {
        limit = DATA_FEED_INTEGRATION_CONFIG.alertHistoryLimit;
    }

    let result = [];

    historyLock.acquire(() => {
        result = [...alertHistory];
        if (limit > 0) {
            result = result.slice(-limit);
        }
    });

    return result;
}

// Función para obtener el estado de la conexión
function getConnectionStatus() {
    "use strict";

    return {
        connected: connected,
        reconnectAttempts: reconnectAttempts,
        lastAlertTime: lastAlertTime ? lastAlertTime.toISOString() : null,
        alertCount: getAlertHistory().length,
        maxAttempts: DATA_FEED_INTEGRATION_CONFIG.maxReconnectAttempts
    };
}

// Función para probar la conexión (para uso en el frontend)
function testConnection() {
    "use strict";

    return new Promise((resolve) => {
        try {
            // Verificar si el servidor HTTP está respondiendo
            fetch(`${DATA_FEED_INTEGRATION_CONFIG.shadowCoreUrl}/api/status`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                mode: 'cors'
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error(`Servidor HTTP no respondió correctamente (código: ${response.status})`);
                }
            })
            .then(data => {
                resolve({
                    status: 'success',
                    message: 'Servidor HTTP accesible',
                    data: data
                });
            })
            .catch(error => {
                resolve({
                    status: 'error',
                    message: `Error al conectar al servidor HTTP: ${error.message}`
                });
            });

        } catch (e) {
            resolve({
                status: 'error',
                message: `Error al probar conexión: ${e.message}`
            });
        }
    });
}

// Función para enviar una alerta de prueba
function sendTestAlert() {
    "use strict";

    return new Promise((resolve) => {
        try {
            fetch(`${DATA_FEED_INTEGRATION_CONFIG.shadowCoreUrl}/api/simulate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                mode: 'cors'
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error(`Servidor no respondió correctamente (código: ${response.status})`);
                }
            })
            .then(data => {
                resolve({
                    status: 'success',
                    message: 'Alerta de prueba enviada',
                    data: data
                });
            })
            .catch(error => {
                resolve({
                    status: 'error',
                    message: `Error al enviar alerta de prueba: ${error.message}`,
                    error: error
                });
            });

        } catch (e) {
            resolve({
                status: 'error',
                message: `Error al enviar alerta de prueba: ${e.message}`
            });
        }
    });
}

// Función para controlar la simulación de alertas
function controlAlertSimulation(action) {
    "use strict";

    return new Promise((resolve) => {
        try {
            fetch(`${DATA_FEED_INTEGRATION_CONFIG.shadowCoreUrl}/api/control`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: action }),
                mode: 'cors'
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error(`Servidor no respondió correctamente (código: ${response.status})`);
                }
            })
            .then(data => {
                resolve({
                    status: 'success',
                    message: data.message || 'Operación completada',
                    data: data
                });
            })
            .catch(error => {
                resolve({
                    status: 'error',
                    message: `Error al controlar simulación: ${error.message}`,
                    error: error
                });
            });

        } catch (e) {
            resolve({
                status: 'error',
                message: `Error al controlar simulación: ${e.message}`
            });
        }
    });
}

// Función para iniciar el módulo de integración
function startDataFeedIntegration() {
    "use strict";

    console.log("Iniciando módulo de integración con el servidor de datos en tiempo real");

    // Intentar conectar inicialmente
    if (!connectToDataFeed()) {
        console.warn("Primera conexión fallida. Iniciando ciclo de reconexión...");
    }

    // Iniciar hilo de reconexión
    handleReconnection();

    // Exponer funciones públicas
    window.DataFeedIntegration = {
        getAlertHistory: getAlertHistory,
        getConnectionStatus: getConnectionStatus,
        processAlert: processAlert,
        subscribeToRooms: subscribeToRooms,
        isConnected: () => connected,
        testConnection: testConnection,
        sendTestAlert: sendTestAlert,
        controlAlertSimulation: controlAlertSimulation,
        config: DATA_FEED_INTEGRATION_CONFIG
    };

    console.log("Módulo de integración iniciado con éxito");
}

// Función para detener el módulo de integración
function stopDataFeedIntegration() {
    "use strict";

    console.log("Deteniendo módulo de integración con el servidor de datos");

    if (socketIoClient) {
        try {
            socketIoClient.disconnect();
            socketIoClient = null;
        } catch (e) {
            console.error("Error al desconectar:", e);
        }
    }

    connected = false;

    // Detener intervalo de reconexión
    if (window.dataFeedReconnectionInterval) {
        clearInterval(window.dataFeedReconnectionInterval);
        delete window.dataFeedReconnectionInterval;
    }

    console.log("Módulo de integración detenido");
}

// Función para inicializar el módulo (para uso en el frontend)
function initDataFeedIntegration() {
    "use strict";

    try {
        // Verificar si ya está inicializado
        if (window.DataFeedIntegration) {
            console.warn("Módulo de integración ya inicializado");
            return false;
        }

        // Iniciar el módulo
        startDataFeedIntegration();

        // Exponer funciones para uso en el frontend
        window.DataFeedIntegration = {
            getAlertHistory: getAlertHistory,
            getConnectionStatus: getConnectionStatus,
            processAlert: processAlert,
            subscribeToRooms: subscribeToRooms,
            isConnected: () => connected,
            testConnection: testConnection,
            sendTestAlert: sendTestAlert,
            controlAlertSimulation: controlAlertSimulation,
            config: DATA_FEED_INTEGRATION_CONFIG
        };

        console.log("Módulo de integración inicializado en el frontend");
        return true;
    } catch (e) {
        console.error("Error al inicializar módulo de integración:", e);
        return false;
    }
}

// Inicializar el módulo cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si Socket.IO está disponible
    if (typeof io !== 'undefined') {
        initDataFeedIntegration();
    } else {
        console.warn("Socket.IO no disponible. Esperando carga desde CDN...");

        // Cargar Socket.IO desde CDN
        const script = document.createElement('script');
        script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
        script.onload = function() {
            initDataFeedIntegration();
        };
        script.onerror = function() {
            console.error("Error al cargar Socket.IO desde CDN");
        };
        document.head.appendChild(script);
    }
});

// Exportar funciones para uso externo
window.DataFeedIntegration = window.DataFeedIntegration || {};
