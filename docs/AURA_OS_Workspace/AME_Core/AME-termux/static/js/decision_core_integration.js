/*
decision_core_integration.js - Integración del Decision Core con el frontend
Este script maneja la comunicación entre el dashboard y el Decision Core,
mostrando los resultados de las decisiones tomadas y el estado del sistema.
*/

// Configuración global
const DecisionCoreIntegration = {
    // Configuración del sistema
    config: {
        serverUrl: 'http://localhost:5002',
        socketUrl: 'http://localhost:5002',
        decisionCorePort: 5003,
        statusInterval: 30000, // 30 segundos
        decisionHistoryLimit: 100
    },

    // Estado de la integración
    state: {
        connected: false,
        decisionCoreStatus: 'desconocido',
        lastDecisionTime: null,
        decisionHistory: [],
        processingAlerts: 0
    },

    // Inicializar la integración
    init: function(config) {
        // Configuración personalizada
        if (config) {
            Object.assign(this.config, config);
        }

        // Configurar eventos del socket
        this.setupSocketEvents();

        // Conectar al servidor
        this.connect();

        // Iniciar intervalo para verificar estado
        this.startStatusInterval();

        // Inicializar UI
        this.initUI();

        console.log('🚀 Decision Core Integration inicializada');
    },

    // Configurar eventos del socket
    setupSocketEvents: function() {
        // Evento de conexión
        socket.on('connect', () => {
            this.state.connected = true;
            this.updateConnectionStatus(true);
            console.log('🔗 Conectado al servidor principal');

            // Suscribirse a salas relevantes
            socket.emit('subscribe', { room: 'global' });
            socket.emit('subscribe', { room: 'decision_engine' });
        });

        // Evento de desconexión
        socket.on('disconnect', () => {
            this.state.connected = false;
            this.updateConnectionStatus(false);
            console.log('⚠️ Desconectado del servidor principal');
        });

        // Evento de nuevo resultado de decisión
        socket.on('decision_result', (resultData) => {
            this.handleDecisionResult(resultData);
        });

        // Evento de estado del Decision Core
        socket.on('agent_status', (statusData) => {
            this.handleAgentStatus(statusData);
        });

        // Evento de alerta procesada (para mostrar en el dashboard)
        socket.on('new_alert', (alertData) => {
            if (alertData.type === 'decision_processed' || alertData.type === 'agent_status') {
                this.handleSystemAlert(alertData);
            }
        });
    },

    // Conectar al servidor
    connect: function() {
        try {
            socket.connect(this.config.socketUrl, {
                transports: ['websocket'],
                query: {
                    'x-decision-core': 'true'
                }
            });
        } catch (e) {
            console.error('Error al conectar al servidor:', e);
        }
    },

    // Desconectar del servidor
    disconnect: function() {
        try {
            if (socket.connected) {
                socket.disconnect();
            }
        } catch (e) {
            console.error('Error al desconectar del servidor:', e);
        }
    },

    // Iniciar intervalo para verificar estado
    startStatusInterval: function() {
        this.statusInterval = setInterval(() => {
            this.checkDecisionCoreStatus();
        }, this.config.statusInterval);
    },

    // Verificar estado del Decision Core
    checkDecisionCoreStatus: function() {
        // En un entorno real, esto haría una solicitud HTTP al Decision Core
        // Por ahora, solo simulamos el estado
        const now = new Date();
        const status = this.state.decisionCoreStatus;

        // Simular cambios de estado
        if (status === 'desconocido' || Math.random() > 0.95) {
            const newStatus = ['operational', 'maintenance', 'error', 'initializing'][Math.floor(Math.random() * 4)];
            this.updateDecisionCoreStatus(newStatus);
        }
    },

    // Actualizar estado de conexión
    updateConnectionStatus: function(connected) {
        this.state.connected = connected;

        // Actualizar UI
        const statusIndicator = document.getElementById('decision-core-status-indicator');
        const statusText = document.getElementById('decision-core-status-text');

        if (statusIndicator && statusText) {
            if (connected) {
                statusIndicator.className = 'status-indicator status-connected';
                statusText.textContent = 'Conectado al Decision Core';
            } else {
                statusIndicator.className = 'status-indicator status-disconnected';
                statusText.textContent = 'Desconectado del Decision Core';
            }
        }

        console.log(`🔗 Estado de conexión: ${connected ? 'Conectado' : 'Desconectado'}`);
    },

    // Actualizar estado del Decision Core
    updateDecisionCoreStatus: function(status) {
        this.state.decisionCoreStatus = status;
        this.state.lastDecisionTime = new Date().toISOString();

        // Actualizar UI
        const statusElement = document.getElementById('decision-core-status-panel');
        if (statusElement) {
            this.renderDecisionCoreStatus(statusElement);
        }

        console.log(`📡 Estado del Decision Core: ${status}`);

        // Enviar evento personalizado
        this.emitSystemEvent('decision_core_status', {
            status: status,
            timestamp: new Date().toISOString()
        });
    },

    // Manejar resultado de decisión
    handleDecisionResult: function(resultData) {
        this.state.processingAlerts = Math.max(0, this.state.processingAlerts - 1);

        // Agregar al historial
        const decisionItem = {
            id: resultData.alert_id,
            type: resultData.alert_type,
            severity: resultData.severity,
            timestamp: resultData.decision_time || resultData.timestamp,
            actions: resultData.actions_taken || 0,
            status: resultData.status,
            details: resultData.details || 'Decisión procesada'
        };

        // Limitar el tamaño del historial
        this.state.decisionHistory.unshift(decisionItem);
        if (this.state.decisionHistory.length > this.config.decisionHistoryLimit) {
            this.state.decisionHistory.pop();
        }

        // Actualizar UI
        this.renderDecisionHistory();

        // Mostrar notificación
        this.showDecisionNotification(decisionItem);

        console.log(`🤖 Decisión procesada: ${resultData.alert_id} (${resultData.alert_type})`);
    },

    // Manejar estado del Decision Core
    handleAgentStatus: function(statusData) {
        this.updateDecisionCoreStatus(statusData.status);

        // Mostrar notificación si es importante
        if (status