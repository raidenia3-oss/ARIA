/*
data_feed_integration.js - Integración mejorada con el Decision Core
Este script maneja la comunicación entre el dashboard y el servidor de datos,
incluyendo la integración con el Decision Core para procesamiento de alertas.
*/

// Configuración global
const DataFeedIntegration = {
    // Configuración del sistema
    config: {
        serverUrl: 'https://aura-server-01.vercel.app',
        socketUrl: 'https://aura-server-01.vercel.app',
        decisionCoreEnabled: true,
        autoConnect: true,
        reconnectAttempts: 5,
        reconnectDelay: 3000
    },

    // Estado de la integración
    state: {
        connected: false,
        socket: null,
        clientId: null,
        rooms: [],
        alertCount: 0,
        lastAlertTime: null,
        connectionAttempts: 0,
        decisionCoreStatus: 'desconocido'
    },

    // Inicializar la integración
    init: function(config) {
        // Configuración personalizada
        if (config) {
            Object.assign(this.config, config);
        }

        // Configurar eventos del socket
        this.setupSocketEvents();

        // Conectar al servidor si está habilitado
        if (this.config.autoConnect) {
            this.connect();
        }

        console.log('🚀 Data Feed Integration inicializada');
    },

    // Configurar eventos del socket
    setupSocketEvents: function() {
        // Evento de conexión
        this.state.socket.on('connect', () => {
            this.state.connected = true;
            this.state.connectionAttempts = 0;
            this.updateConnectionStatus(true);

            // Generar un ID único para el cliente
            this.state.clientId = 'client_' + Math.random().toString(36).substr(2, 9);

            console.log('🔗 Conectado al servidor de datos');
            console.log(`📡 ID de cliente: ${this.state.clientId}`);

            // Suscribirse a salas relevantes
            this.subscribeToRoom('global');
            this.subscribeToRoom('security_alerts');
            this.subscribeToRoom('osint_alerts');

            // Emitir evento de conexión
            this.emitSystemEvent('connected', {
                clientId: this.state.clientId,
                timestamp: new Date().toISOString()
            });
        });

        // Evento de desconexión
        this.state.socket.on('disconnect', () => {
            this.state.connected = false;
            this.updateConnectionStatus(false);

            console.log('⚠️ Desconectado del servidor de datos');

            // Intentar reconectar si no hemos superado el límite de intentos
            if (this.state.connectionAttempts < this.config.reconnectAttempts) {
                this.state.connectionAttempts++;
                console.log(`🔄 Intentando reconectar (${this.state.connectionAttempts}/${this.config.reconnectAttempts})...`);
                setTimeout(() => {
                    this.connect();
                }, this.config.reconnectDelay);
            } else {
                console.log('❌ Máximo de intentos de reconexión alcanzado');
                this.emitSystemEvent('disconnected', {
                    message: 'Máximo de intentos de reconexión alcanzado',
                    timestamp: new Date().toISOString()
                });
            }
        });

        // Evento de reconexión
        this.state.socket.on('reconnect', () => {
            console.log('🔄 Reconectado al servidor de datos');
            this.emitSystemEvent('reconnected', {
                timestamp: new Date().toISOString()
            });
        });

        // Evento de reconexión fallida
        this.state.socket.on('reconnect_failed', () => {
            console.log('❌ Reconexión fallida');
            this.emitSystemEvent('reconnect_failed', {
                timestamp: new Date().toISOString()
            });
        });

        // Evento de nueva alerta
        this.state.socket.on('new_alert', (alertData) => {
            this.handleNewAlert(alertData);
        });

        // Evento de sistema
        this.state.socket.on('system_message', (messageData) => {
            this.handleSystemMessage(messageData);
        });

        // Evento de configuración actualizada
        this.state.socket.on('config_update', (configData) => {
            this.handleConfigUpdate(configData);
        });

        // Evento de resultado de decisión (del Decision Core)
        this.state.socket.on('decision_result', (resultData) => {
            this.handleDecisionResult(resultData);
        });

        // Evento de estado del Decision Core
        this.state.socket.on('agent_status', (statusData) => {
            this.handleAgentStatus(statusData);
        });
    },

    // Conectar al servidor
    connect: function() {
        try {
            if (!this.state.socket) {
                this.state.socket = io(this.config.socketUrl, {
                    transports: ['websocket'],
                    query: {
                        'client_id': this.state.clientId,
                        'dashboard_version': '1.0.0'
                    }
                });
            }

            this.state.socket.connect();
            return true;
        } catch (e) {
            console.error('Error al conectar al servidor:', e);
            return false;
        }
    },

    // Desconectar del servidor
    disconnect: function() {
        try {
            if (this.state.socket && this.state.socket.connected) {
                this.state.socket.disconnect();
            }
            return true;
        } catch (e) {
            console.error('Error al desconectar del servidor:', e);
            return false;
        }
    },

    // Suscribirse a una sala
    subscribeToRoom: function(roomName) {
        if (this.state.connected && this.state.socket) {
            try {
                this.state.socket.emit('subscribe', { room: roomName });
                if (!this.state.rooms.includes(roomName)) {
                    this.state.rooms.push(roomName);
                }
                console.log(`📡 Suscripto a sala: ${roomName}`);
            } catch (e) {
                console.error(`Error al suscribirse a ${roomName}:`, e);
            }
        }
    },

    // Actualizar estado de conexión
    updateConnectionStatus: function(connected) {
        this.state.connected = connected;

        // Actualizar UI
        const statusIndicator = document.getElementById('connection-status-indicator');
        const statusText = document.getElementById('connection-status-text');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');

        if (statusIndicator && statusText) {
            if (connected) {
                statusIndicator.className = 'status-indicator status-connected';
                statusText.textContent = 'Conectado';
            } else {
                statusIndicator.className = 'status-indicator status-disconnected';
                statusText.textContent = 'Desconectado';
            }
        }

        if (connectBtn && disconnectBtn) {
            connectBtn.disabled = connected;
            disconnectBtn.disabled = !connected;
        }

        console.log(`🔗 Estado de conexión: ${connected ? 'Conectado' : 'Desconectado'}`);

        // Emitir evento de estado
        this.emitSystemEvent('connection_status', {
            connected: connected,
            timestamp: new Date().toISOString()
        });
    },

    // Manejar nueva alerta
    handleNewAlert: function(alertData) {
        this.state.alertCount++;
        this.state.lastAlertTime = new Date().toISOString();

        // Mostrar alerta en el dashboard
        this.showAlert(alertData);

        // Emitir evento personalizado
        this.emitSystemEvent('new_alert', alertData);

        console.log(`🚨 Nueva alerta recibida: ${alertData.id} (${alertData.type})`);
    },

    // Manejar mensaje del sistema
    handleSystemMessage: function(messageData) {
        // Mostrar mensaje en el dashboard
        this.showSystemMessage(messageData);

        // Emitir evento personalizado
        this.emitSystemEvent('system_message', messageData);

        console.log(`📢 Mensaje del sistema: ${messageData.message}`);
    },

    // Manejar actualización de configuración
    handleConfigUpdate: function(configData) {
        // Guardar configuración global
        this.config.threatLevels = configData.threat_levels || {};
        this.config.nodeMapping = configData.node_mapping || {};
        this.config.dataSources = configData.data_sources || {};

        // Mostrar notificación de configuración actualizada
        this.showSystemMessage({
            type: 'info',
            message: 'Configuración del sistema actualizada',
            timestamp: new Date().toISOString()
        });

        // Emitir evento personalizado
        this.emitSystemEvent('config_updated', configData);

        console.log('🔄 Configuración del sistema actualizada');
    },

    // Manejar resultado de decisión
    handleDecisionResult: function(resultData) {
        // Mostrar resultado de decisión en el dashboard
        this.showDecisionResult(resultData);

        // Emitir evento personalizado
        this.emitSystemEvent('decision_result', resultData);

        console.log(`🤖 Resultado de decisión: ${resultData.alert_id} (${resultData.alert_type})`);
    },

    // Manejar estado del Decision Core
    handleAgentStatus: function(statusData) {
        this.state.decisionCoreStatus = statusData.status;

        // Mostrar estado del Decision Core
        this.showAgentStatus(statusData);

        // Emitir evento personalizado
        this.emitSystemEvent('agent_status', statusData);

        console.log(`📡 Estado del Decision Core: ${statusData.status}`);
    },

    // Mostrar alerta en el dashboard
    showAlert: function(alertData) {
        // Determinar el contenedor de alertas
        const alertList = document.getElementById('alert-list');
        if (!alertList) return;

        // Crear elemento de alerta
        const alertItem = document.createElement('div');
        alertItem.className = 'osint-alert-item';
        alertItem.dataset.alertId = alertData.id;

        // Determinar el icono y color según el tipo de alerta
        let iconClass = 'fas fa-exclamation-triangle';
        let severityClass = 'severity-info';
        let badgeClass = 'alert-type-badge alert-type-info';

        if (alertData.type === 'phishing') {
            iconClass = 'fas fa-fish';
            severityClass = 'severity-critical';
            badgeClass = 'alert-type-badge alert-type-phishing';
        } else if (alertData.type === 'scan') {
            iconClass = 'fas fa-search';
            severityClass = 'severity-high';
            badgeClass = 'alert-type-badge alert-type-scan';
        } else if (alertData.type === 'leak') {
            iconClass = 'fas fa-database-leak';
            severityClass = 'severity-medium';
            badgeClass = 'alert-type-badge alert-type-leak';
        } else if (alertData.type === 'malware') {
            iconClass = 'fas fa-virus';
            severityClass = 'severity-critical';
            badgeClass = 'alert-type-badge alert-type-malware';
        } else if (alertData.type === 'decision_processed') {
            iconClass = 'fas fa-robot';
            severityClass = 'severity-info';
            badgeClass = 'alert-type-badge alert-type-decision';
        } else if (alertData.type === 'agent_status') {
            iconClass = 'fas fa-cog';
            severityClass = 'severity-info';
            badgeClass = 'alert-type-badge alert-type-status';
        }

        // Crear el HTML de la alerta
        alertItem.innerHTML = `
            <div class="alert-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="alert-info">
                <div class="alert-title">${alertData.title}</div>
                <div class="alert-source">${alertData.source}</div>
                <div class="alert-severity">
                    <span class="severity-indicator ${severityClass}"></span>
                    <span>Severidad: ${alertData.severity}</span>
                    <span class="${badgeClass}">${alertData.type}</span>
                </div>
            </div>
            <div class="alert-actions">
                <button class="alert-action" data-action="view">
                    <i class="fas fa-eye"></i>
                </button>
                ${this.config.decisionCoreEnabled && alertData.type !== 'decision_processed' && alertData.type !== 'agent_status' ?
                    `<button class="alert-action" data-action="decision">
                        <i class="fas fa-brain"></i>
                    </button>` : ''}
                ${alertData.type === 'decision_processed' ?
                    `<button class="alert-action" data-action="view-details">
                        <i class="fas fa-info-circle"></i>
                    </button>` : ''}
            </div>
        `;

        // Agregar evento para ver detalles de la alerta
        alertItem.querySelector('[data-action="view"]').addEventListener('click', () => {
            this.showAlertDetails(alertData);
        });

        // Agregar evento para ver detalles de decisión
        if (alertItem.querySelector('[data-action="view-details"]')) {
            alertItem.querySelector('[data-action="view-details"]').addEventListener('click', () => {
                this.showDecisionDetails(alertData);
            });
        }

        // Agregar evento para procesar con Decision Core
        if (this.config.decisionCoreEnabled && alertItem.querySelector('[data-action="decision"]')) {
            alertItem.querySelector('[data-action="decision"]').addEventListener('click', () => {
                this.processWithDecisionCore(alertData);
            });
        }

        // Agregar la alerta a la lista
        alertList.insertBefore(alertItem, alertList.firstChild);

        // Mostrar la alerta más reciente en el panel de detalles si es una alerta normal
        if (alertData.type !== 'decision_processed' && alertData.type !== 'agent_status') {
            this.showAlertDetails(alertData);
        }
    },

    // Mostrar detalles de una alerta
    showAlertDetails: function(alertData) {
        const detailsPanel = document.getElementById('alert-details-panel');
        if (!detailsPanel) return;

        const titleElement = document.getElementById('alert-title');
        const sourceElement = document.getElementById('alert-source');
        const severityElement = document.getElementById('alert-severity');
        const descriptionElement = document.getElementById('alert-description');
        const metadataElement = document.getElementById('alert-metadata');

        if (!titleElement || !sourceElement || !severityElement || !descriptionElement || !metadataElement) return;

        // Determinar el color de severidad
        let severityClass = 'severity-info';
        if (alertData.severity === 'critical') {
            severityClass = 'severity-critical';
        } else if (alertData.severity === 'high') {
            severityClass = 'severity-high';
        } else if (alertData.severity === 'medium') {
            severityClass = 'severity-medium';
        } else if (alertData.severity === 'low') {
            severityClass = 'severity-low';
        }

        // Actualizar el panel de detalles
        titleElement.textContent = alertData.title;
        sourceElement.textContent = `Fuente: ${alertData.source}`;
        severityElement.innerHTML = `
            <span class="severity-indicator ${severityClass}"></span>
            <span>Severidad: ${alertData.severity}</span>
        `;
        descriptionElement.innerHTML = `<p>${alertData.description || 'No hay descripción disponible'}</p>`;

        // Limpiar metadatos anteriores
        metadataElement.innerHTML = '';

        // Agregar metadatos
        if (alertData.metadata) {
            for (const [key, value] of Object.entries(alertData.metadata)) {
                const metadataItem = document.createElement('div');
                metadataItem.className = 'metadata-item';
                metadataItem.innerHTML = `
                    <div class="metadata-label">${key}</div>
                    <div class="metadata-value">${value}</div>
                `;
                metadataElement.appendChild(metadataItem);
            }
        }

        // Mostrar detalles si no están visibles
        if (detailsPanel.style.display === 'none') {
            detailsPanel.style.display = 'block';
        }

        // Mostrar detalles adicionales si existen
        if (alertData.details && alertData.details.length > 0) {
            const detailsSection = document.createElement('div');
            detailsSection.className = 'alert-details';
            detailsSection.innerHTML = `
                <div class="metadata-title">Detalles adicionales</div>
                <div class="metadata-grid">
                    ${alertData.details.map(detail =>
                        `<div class="metadata-item">
                            <div class="metadata-label">${detail.type}</div>
                            <div class="metadata-value">${JSON.stringify(detail.value)}</div>
                        </div>`
                    ).join('')}
                </div>
            `;
            descriptionElement.appendChild(detailsSection);
        }

        // Mostrar botones de acción según el tipo de alerta
        const actionsContainer = document.querySelector('.alert-actions');
        if (actionsContainer) {
            actionsContainer.innerHTML = `
                <button class="alert-action" id="acknowledge-btn">
                    <i class="fas fa-check-circle"></i> Acknowledge
                </button>
                <button class="alert-action" id="ignore-btn">
                    <i class="fas fa-times-circle"></i> Ignorar
                </button>
                ${this.config.decisionCoreEnabled ?
                    `<button class="alert-action" id="decision-btn">
                        <i class="fas fa-brain"></i> Procesar con Decision Core
                    </button>` : ''}
            `;

            // Agregar eventos a los botones
            document.getElementById('acknowledge-btn').addEventListener('click', () => {
                this.acknowledgeAlert(alertData.id);
            });

            document.getElementById('ignore-btn').addEventListener('click', () => {
                this.ignoreAlert(alertData.id);
            });

            if (this.config.decisionCoreEnabled) {
                document.getElementById('decision-btn').addEventListener('click', () => {
                    this.processWithDecisionCore(alertData);
                });
            }
        }
    },

    // Mostrar detalles de una decisión
    showDecisionDetails: function(decisionData) {
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
                        <span class="detail-label">ID de alerta:</span>
                        <span class="detail-value">${decisionData.metadata?.original_alert || 'Desconocido'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Tipo:</span>
                        <span class="detail-value">${decisionData.type}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Estado:</span>
                        <span class="detail-value ${decisionData.status === 'error' ? 'error' : 'success'}">
                            ${decisionData.status}
                        </span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Acciones tomadas:</span>
                        <span class="detail-value">${decisionData.metadata?.actions_taken || 0}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Fecha:</span>
                        <span class="detail-value">${new Date(decisionData.timestamp).toLocaleString()}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Detalles:</span>
                        <div class="detail-value details-text">${decisionData.description || 'No hay detalles disponibles'}</div>
                    </div>
                    ${decisionData.metadata ?
                        `<div class="detail-row">
                            <span class="detail-label">Metadatos:</span>
                            <div class="detail-value details-text">
                                <pre>${JSON.stringify(decisionData.metadata, null, 2)}</pre>
                            </div>
                        </div>` : ''}
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

    // Mostrar resultado de decisión
    showDecisionResult: function(resultData) {
        // Mostrar notificación
        this.showSystemMessage({
            type: 'info',
            message: `Decisión procesada: ${resultData.alert_type} (${resultData.status})`,
            details: resultData.details,
            timestamp: new Date().toISOString()
        });

        // Mostrar alerta en el dashboard
        this.showAlert({
            id: `decision_${resultData.alert_id}`,
            timestamp: resultData.decision_time || resultData.timestamp,
            source: 'decision_engine',
            type: 'decision_processed',
            severity: 'info',
            title: `Decisión: ${resultData.alert_type}`,
            description: resultData.details || 'Decisión procesada',
            metadata: {
                actions_taken: resultData.actions_taken,
                status: resultData.status,
                original_alert: resultData.alert_id
            }
        });
    },

    // Mostrar estado del Decision Core
    showAgentStatus: function(statusData) {
        // Actualizar el estado en el panel del Decision Core
        if (window.DecisionCoreIntegration) {
            window.DecisionCoreIntegration.updateDecisionCoreStatus(statusData.status);
        }

        // Mostrar notificación
        let messageType = 'info';
        let message = `Estado del Decision Core: ${statusData.status}`;

        if (statusData.status === 'error') {
            messageType = 'error';
            message = `❌ ERROR en Decision Core: ${statusData.message || 'Estado desconocido'}`;
        } else if (statusData.status === 'disconnected') {
            messageType = 'warning';
            message = `⚠️ Decision Core desconectado: ${statusData.message || 'Conexión perdida'}`;
        } else if (statusData.status === 'connected') {
            messageType = 'success';
            message = `✅ Decision Core conectado y operativo`;
        }

        this.showSystemMessage({
            type: messageType,
            message: message,
            timestamp: new Date().toISOString()
        });
    },

    // Mostrar mensaje del sistema
    showSystemMessage: function(messageData) {
        // Crear notificación en el dashboard
        const notification = document.createElement('div');
        notification.className = `system-notification ${messageData.type || 'info'}`;

        let iconClass = 'fas fa-info-circle';
        if (messageData.type === 'error') {
            iconClass = 'fas fa-exclamation-triangle';
        } else if (messageData.type === 'warning') {
            iconClass = 'fas fa-exclamation';
        } else if (messageData.type === 'success') {
            iconClass = 'fas fa-check-circle';
        }

        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">
                    <i class="${iconClass}"></i>
                </span>
                <span class="notification-message">
                    ${messageData.message}
                </span>
                <span class="notification-time">${new Date().toLocaleTimeString()}</span>
            </div>
        `;

        // Agregar al dashboard
        const dashboard = document.querySelector('.osint-dashboard');
        if (dashboard) {
            const notificationsContainer = document.createElement('div');
            notificationsContainer.className = 'system-notifications-container';

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

    // Procesar alerta con Decision Core
    processWithDecisionCore: function(alertData) {
        if (!this.config.decisionCoreEnabled || !this.state.connected) {
            this.showSystemMessage({
                type: 'warning',
                message: 'Decision Core no disponible o no conectado al servidor',
                timestamp: new Date().toISOString()
            });
            return;
        }

        try {
            // Mostrar notificación de procesamiento
            this.showSystemMessage({
                type: 'info',
                message: `🤖 Procesando alerta con Decision Core: ${alertData.title}`,
                timestamp: new Date().toISOString()
            });

            // En un entorno real, esto enviaría la alerta al Decision Core
            // Por ahora, simulamos el procesamiento

            // Simular resultado después de 2 segundos
            setTimeout(() => {
                // Crear resultado simulado
                const resultData = {
                    alert_id: alertData.id,
                    alert_type: alertData.type,
                    severity: alertData.severity,
                    timestamp: alertData.timestamp,
                    actions_taken: 2,
                    status: 'success',
                    details: `Alerta "${alertData.title}" procesada por Decision Core`,
                    decision_time: new Date().toISOString()
                };

                // Mostrar resultado
                this.showDecisionResult(resultData);

                // Emitir evento personalizado
                this.emitSystemEvent('decision_processed', resultData);
            }, 2000);

        } catch (e) {
            console.error('Error al procesar alerta con Decision Core:', e);
            this.showSystemMessage({
                type: 'error',
                message: `❌ Error al procesar alerta con Decision Core: ${e.message}`,
                timestamp: new Date().toISOString()
            });
        }
    },

    // Acknowledge una alerta
    acknowledgeAlert: function(alertId) {
        if (!this.state.connected) {
            this.showSystemMessage({
                type: 'warning',
                message: 'No conectado al servidor. No se pudo acknowledge la alerta',
                timestamp: new Date().toISOString()
            });
            return;
        }

        try {
            // En un entorno real, esto enviaría una solicitud al servidor
            // Por ahora, solo simulamos la acción
            this.showSystemMessage({
                type: 'success',
                message: `✅ Alerta ${alertId} marcada como leída`,
                timestamp: new Date().toISOString()
            });

            // Emitir evento personalizado
            this.emitSystemEvent('alert_acknowledged', {
                alert_id: alertId,
                timestamp: new Date().toISOString()
            });

        } catch (e) {
            console.error('Error al acknowledge alerta:', e);
            this.showSystemMessage({
                type: 'error',
                message: `❌ Error al acknowledge alerta: ${e.message}`,
                timestamp: new Date().toISOString()
            });
        }
    },

    // Ignorar una alerta
    ignoreAlert: function(alertId) {
        if (!this.state.connected) {
            this.showSystemMessage({
                type: 'warning',
                message: 'No conectado al servidor. No se pudo ignorar la alerta',
                timestamp: new Date().toISOString()
            });
            return;
        }

        try {
            // En un entorno real, esto enviaría una solicitud al servidor
            // Por ahora, solo simulamos la acción
            this.showSystemMessage({
                type: 'info',
                message: `ℹ️ Alerta ${alertId} ignorada`,
                timestamp: new Date().toISOString()
            });

            // Emitir evento personalizado
            this.emitSystemEvent('alert_ignored', {
                alert_id: alertId,
                timestamp: new Date().toISOString()
            });

        } catch (e) {
            console.error('Error al ignorar alerta:', e);
            this.showSystemMessage({
                type: 'error',
                message: `❌ Error al ignorar alerta: ${e.message}`,
                timestamp: new Date().toISOString()
            });
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
    },

    // Actualizar la lista de alertas
    refreshAlerts: function() {
        if (!this.state.connected) {
            this.showSystemMessage({
                type: 'warning',
                message: 'No conectado al servidor. No se pueden actualizar las alertas',
                timestamp: new Date().toISOString()
            });
            return;
        }

        try {
            // En un entorno real, esto enviaría una solicitud para refrescar alertas
            // Por ahora, solo simulamos la acción
            this.showSystemMessage({
                type: 'info',
                message: '🔄 Lista de alertas actualizada',
                timestamp: new Date().toISOString()
            });

            // Emitir evento personalizado
            this.emitSystemEvent('alerts_refreshed', {
                timestamp: new Date().toISOString()
            });

        } catch (e) {
            console.error('Error al actualizar alertas:', e);
            this.showSystemMessage({
                type: 'error',
                message: `❌ Error al actualizar alertas: ${e.message}`,
                timestamp: new Date().toISOString()
            });
        }
    }
};

// Inicializar la integración cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Verificar si el DataFeedIntegration ya está inicializado
    if (!window.DataFeedIntegrationInitialized) {
        window.DataFeedIntegrationInitialized = true;

        // Configuración específica para el dashboard OSINT
        const config = {
            serverUrl: 'https://aura-server-01.vercel.app',
            socketUrl: 'https://aura-server-01.vercel.app',
            decisionCoreEnabled: true,
            autoConnect: true,
            reconnectAttempts: 5,
            reconnectDelay: 3000
        };

        // Inicializar la integración
        DataFeedIntegration.init(config);

        console.log('🚀 Data Feed Integration inicializada en el dashboard OSINT');
    }
});
