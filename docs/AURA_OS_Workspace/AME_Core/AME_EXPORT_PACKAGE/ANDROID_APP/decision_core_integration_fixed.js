/*
decision_core_integration.js - Integración del Decision Core con el frontend (versión corregida)
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
        if (statusData.status === 'error' || statusData.status === 'disconnected') {
            this.showStatusNotification(statusData.status, statusData.message);
        }

        console.log(`📡 Estado del Decision Core actualizado: ${statusData.status}`);
    },

    // Manejar alertas del sistema
    handleSystemAlert: function(alertData) {
        // Implementar lógica para mostrar alertas del sistema
        console.log(`📢 Alerta del sistema: ${alertData.title}`);
    },

    // Inicializar UI
    initUI: function() {
        // Crear panel de estado del Decision Core si no existe
        if (!document.getElementById('decision-core-status-panel')) {
            this.createDecisionCoreStatusPanel();
        }

        // Crear sección de historial de decisiones si no existe
        if (!document.getElementById('decision-core-history')) {
            this.createDecisionHistorySection();
        }
    },

    // Crear panel de estado del Decision Core
    createDecisionCoreStatusPanel: function() {
        const panel = document.createElement('div');
        panel.id = 'decision-core-status-panel';
        panel.className = 'decision-core-status-panel';

        panel.innerHTML = `
            <div class="decision-core-header">
                <h3>🤖 Decision Core Status</h3>
                <div class="connection-status">
                    <span class="status-indicator status-disconnected" id="decision-core-status-indicator"></span>
                    <span id="decision-core-status-text">Desconectado</span>
                </div>
            </div>
            <div class="decision-core-details">
                <div class="detail-row">
                    <span class="detail-label">Estado:</span>
                    <span class="detail-value" id="decision-core-status-value">Desconocido</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Última actualización:</span>
                    <span class="detail-value" id="decision-core-last-update">Nunca</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Alertas procesadas:</span>
                    <span class="detail-value" id="decision-core-alerts-processed">0</span>
                </div>
            </div>
        `;

        // Agregar al dashboard
        const dashboard = document.querySelector('.osint-dashboard');
        if (dashboard) {
            const sidebar = document.createElement('div');
            sidebar.className = 'decision-core-sidebar';
            sidebar.appendChild(panel);

            // Insertar después del panel de detalles de alertas
            const alertDetails = document.querySelector('.osint-details-panel');
            if (alertDetails) {
                dashboard.insertBefore(sidebar, alertDetails.nextSibling);
            } else {
                dashboard.appendChild(sidebar);
            }
        }

        console.log('📊 Panel de estado del Decision Core creado');
    },

    // Crear sección de historial de decisiones
    createDecisionHistorySection: function() {
        const historyContainer = document.createElement('div');
        historyContainer.id = 'decision-core-history';
        historyContainer.className = 'decision-core-history';

        historyContainer.innerHTML = `
            <div class="history-header">
                <h3>📜 Historial de Decisiones</h3>
                <div class="history-controls">
                    <button class="history-clear-btn" id="clear-decision-history">Limpiar</button>
                </div>
            </div>
            <div class="history-list" id="decision-history-list">
                <div class="history-empty">No hay decisiones registradas</div>
            </div>
        `;

        // Agregar al dashboard
        const dashboard = document.querySelector('.osint-dashboard');
        if (dashboard) {
            const sidebar = document.querySelector('.decision-core-sidebar');
            if (sidebar) {
                sidebar.appendChild(historyContainer);
            } else {
                dashboard.appendChild(historyContainer);
            }
        }

        // Agregar evento para limpiar historial
        document.getElementById('clear-decision-history').addEventListener('click', () => {
            this.state.decisionHistory = [];
            this.renderDecisionHistory();
        });

        console.log('📜 Sección de historial de decisiones creada');
    },

    // Renderizar estado del Decision Core
    renderDecisionCoreStatus: function(element) {
        if (!element) {
            element = document.getElementById('decision-core-status-panel');
            if (!element) return;
        }

        const statusValue = document.getElementById('decision-core-status-value');
        const lastUpdate = document.getElementById('decision-core-last-update');
        const alertsProcessed = document.getElementById('decision-core-alerts-processed');

        if (statusValue) statusValue.textContent = this.state.decisionCoreStatus || 'Desconocido';
        if (lastUpdate) lastUpdate.textContent = this.state.lastDecisionTime || 'Nunca';
        if (alertsProcessed) alertsProcessed.textContent = this.state.decisionHistory.length || '0';
    },

    // Renderizar historial de decisiones
    renderDecisionHistory: function() {
        const historyList = document.getElementById('decision-history-list');
        if (!historyList) return;

        if (this.state.decisionHistory.length === 0) {
            historyList.innerHTML = '<div class="history-empty">No hay decisiones registradas</div>';
            return;
        }

        // Ordenar por fecha (la más reciente primero)
        const sortedHistory = [...this.state.decisionHistory].sort((a, b) => {
            return new Date(b.timestamp) - new Date(a.timestamp);
        });

        // Limitar a los últimos 50 elementos
        const displayHistory = sortedHistory.slice(0, 50);

        let html = '';
        displayHistory.forEach((decision, index) => {
            // Determinar clase de severidad
            let severityClass = 'history-item';
            if (decision.status === 'error') {
                severityClass += ' error';
            } else if (decision.severity === 'Crítica' || decision.severity === 'Alta') {
                severityClass += ' high';
            } else if (decision.severity === 'Media') {
                severityClass += ' medium';
            }

            html += `
                <div class="${severityClass}" data-index="${index}">
                    <div class="history-item-header">
                        <span class="history-item-id">${decision.id}</span>
                        <span class="history-item-type">${decision.type}</span>
                        <span class="history-item-severity">${decision.severity}</span>
                        <span class="history-item-time">${new Date(decision.timestamp).toLocaleString()}</span>
                    </div>
                    <div class="history-item-details">
                        <div class="history-item-actions">${decision.actions} acciones</div>
                        <div class="history-item-status">${decision.status}</div>
                        <div class="history-item-summary">${decision.details}</div>
                    </div>
                </div>
            `;
        });

        historyList.innerHTML = html;

        // Agregar eventos para mostrar detalles completos
        document.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = item.getAttribute('data-index');
                const decision = displayHistory[index];
                this.showDecisionDetails(decision);
            });
        });
    },

    // Mostrar detalles de una decisión
    showDecisionDetails: function(decision) {
        const detailsModal = document.createElement('div');
        detailsModal.className = 'decision-details-modal';
        detailsModal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Detalles de Decisión</h3>
                    <span class="modal-close">&times;</span>
                </div>
                <div class="modal-body">
                    <div class="detail-row">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${decision.id}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Tipo:</span>
                        <span class="detail-value">${decision.type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Severidad:</span>
                        <span class="detail-value">${decision.severity}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fecha:</span>
                        <span class="detail-value">${new Date(decision.timestamp).toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Estado:</span>
                        <span class="detail-value ${decision.status === 'error' ? 'error' : 'success'}">
                            ${decision.status}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Acciones:</span>
                        <span class="detail-value">${decision.actions}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Detalles:</span>
                        <div class="detail-value details-text">${decision.details}</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-close-btn">Cerrar</button>
                </div>
            </div>
        `;

        // Agregar al body
        document.body.appendChild(detailsModal);

        // Cerrar modal
        detailsModal.querySelector('.modal-close').addEventListener('click', () => {
            document.body.removeChild(detailsModal);
        });

        detailsModal.querySelector('.modal-close-btn').addEventListener('click', () => {
            document.body.removeChild(detailsModal);
        });

        detailsModal.querySelector('.modal-overlay').addEventListener('click', () => {
            document.body.removeChild(detailsModal);
        });
    },

    // Mostrar notificación de decisión
    showDecisionNotification: function(decision) {
        // Implementar notificación visual
        console.log(`📢 Notificación: ${decision.details}`);

        // Crear notificación en el dashboard
        const notification = document.createElement('div');
        notification.className = `decision-notification ${decision.status === 'error' ? 'error' : 'success'}`;

        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">🤖</span>
                <span class="notification-message">
                    Decisión procesada: ${decision.details}
                </span>
                <span class="notification-time">${new Date().toLocaleTimeString()}</span>
            </div>
        `;

        // Agregar al dashboard
        const dashboard = document.querySelector('.osint-dashboard');
        if (dashboard) {
            const notificationsContainer = document.createElement('div');
            notificationsContainer.className = 'decision-notifications-container';

            dashboard.insertBefore(notificationsContainer, dashboard.firstChild);
            notificationsContainer.appendChild(notification);

            // Eliminar notificación después de 5 segundos
            setTimeout(() => {
                if (notificationsContainer && notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 5000);
        }
    },

    // Mostrar notificación de estado
    showStatusNotification: function(status, message) {
        // Implementar notificación visual para estado importante
        console.log(`📢 Estado importante: ${status} - ${message}`);

        // Crear notificación en el dashboard
        const notification = document.createElement('div');
        notification.className = `decision-notification ${status === 'error' ? 'error' : 'warning'}`;

        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">⚠️</span>
                <span class="notification-message">
                    ${status === 'error' ? 'ERROR' : 'ADVERTENCIA'} en Decision Core: ${message}
                </span>
                <span class="notification-time">${new Date().toLocaleTimeString()}</span>
            </div>
        `;

        // Agregar al dashboard
        const dashboard = document.querySelector('.osint-dashboard');
        if (dashboard) {
            const notificationsContainer = document.querySelector('.decision-notifications-container');
            if (!notificationsContainer) {
                const container = document.createElement('div');
                container.className = 'decision-notifications-container';
                dashboard.insertBefore(container, dashboard.firstChild);
            } else {
                dashboard.insertBefore(notificationsContainer, dashboard.firstChild);
            }

            notificationsContainer.appendChild(notification);

            // Eliminar notificación después de 10 segundos
            setTimeout(() => {
                if (notificationsContainer && notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 10000);
        }
    },

    // Emitir evento personalizado
    emitSystemEvent: function(eventName, data) {
        try {
            // En un entorno real, esto emitiría un evento personalizado
            console.log(`📡 Evento emitido: ${eventName}`, data);

            // Simular evento para el dashboard
            const event = new CustomEvent(eventName, {
                detail: data,
                bubbles: true
            });
            document.dispatchEvent(event);
        } catch (e) {
            console.error('Error al emitir evento:', e);
        }
    }
};

// Inicializar la integración cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Verificar si el Decision Core Integration ya está inicializado
    if (!window.DecisionCoreIntegrationInitialized) {
        window.DecisionCoreIntegrationInitialized = true;

        // Configuración específica para el dashboard OSINT
        const config = {
            serverUrl: 'http://localhost:5002',
            socketUrl: 'http://localhost:5002',
            decisionCorePort: 5003,
            statusInterval: 30000,
            decisionHistoryLimit: 100
        };

        // Inicializar la integración
        DecisionCoreIntegration.init(config);

        console.log('🚀 Decision Core Integration inicializada en el dashboard OSINT');
    }
});