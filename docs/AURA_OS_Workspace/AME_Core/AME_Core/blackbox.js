/**
 * BlackBox.js - Módulo para manejar la Caja Negra de logs
 * Incluye efectos tipowriter y polling de logs
 */

class BlackBox {
    constructor() {
        this.terminal = document.getElementById('blackBoxTerminal');
        this.toggleButton = document.getElementById('blackBoxToggle');
        this.contentDiv = document.getElementById('blackBoxContent');
        this.tabs = document.querySelectorAll('.black-box-tab');
        this.lockButton = document.getElementById('blackBoxLock');
        this.activeTab = 'system';
        this.pollingInterval = 3000; // 3 segundos
        this.pollingActive = false;
        this.lastLogTime = 0;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadInitialLogs();
        this.startPolling();
    }

    setupEventListeners() {
        // Toggle para mostrar/ocultar la terminal
        if (this.toggleButton) {
            this.toggleButton.addEventListener('click', () => {
                this.toggleTerminal();
            });
        }

        // Pestañas para cambiar de tipo de log
        if (this.tabs) {
            this.tabs.forEach(tab => {
                if (tab) {
                    tab.addEventListener('click', () => {
                        this.changeTab(tab.dataset.tab);
                    });
                }
            });
        }

        // Botón de candado
        if (this.lockButton) {
            this.lockButton.addEventListener('click', () => {
                this.toggleLock();
            });
        }
    }

    toggleTerminal() {
        if (this.terminal) {
            this.terminal.style.display = this.terminal.style.display === 'none' ? 'block' : 'none';
            if (this.toggleButton) {
                this.toggleButton.classList.toggle('active');
            }
        }
    }

    toggleLock() {
        if (this.lockButton) {
            this.lockButton.classList.toggle('locked');
        }
    }

    changeTab(tabName) {
        if (!this.tabs) return;

        this.tabs.forEach(tab => {
            if (tab) {
                tab.classList.remove('active');
                if (tab.dataset.tab === tabName) {
                    tab.classList.add('active');
                }
            }
        });

        this.activeTab = tabName;
        this.loadLogs();
    }

    loadInitialLogs() {
        this.loadLogs();
    }

    loadLogs() {
        if (!this.contentDiv) return;

        fetch(`/api/tactical/logs`)
            .then(response => response.json())
            .then(data => {
                this.processLogs(data);
            })
            .catch(error => {
                console.error('Error al cargar logs:', error);
                this.showError('Error al cargar logs: ' + error.message);
            });
    }

    processLogs(data) {
        if (!data || !data.logs || !data.logs[this.activeTab]) {
            this.showError('No hay logs disponibles para este tipo.');
            return;
        }

        const logs = data.logs[this.activeTab].entries || [];
        if (!this.contentDiv) return;

        this.contentDiv.innerHTML = '';

        if (logs.length === 0) {
            this.showInfo('No hay registros disponibles.');
            return;
        }

        logs.forEach(log => {
            const logElement = this.createLogElement(log);
            this.contentDiv.appendChild(logElement);
        });

        // Auto-scroll al final
        this.contentDiv.scrollTop = this.contentDiv.scrollHeight;
    }

    createLogElement(log) {
        const logElement = document.createElement('div');
        logElement.className = 'black-box-log-entry';

        // Determinar el tipo de log
        if (log.includes('ERROR') || log.includes('❌') || log.includes('⚠')) {
            logElement.classList.add('error');
        } else if (log.includes('WARNING') || log.includes('⚠️')) {
            logElement.classList.add('warning');
        } else if (log.includes('EMERGENCY') || log.includes('🚨')) {
            logElement.classList.add('emergency');
        } else if (log.includes('INFO') || log.includes('📡')) {
            logElement.classList.add('info');
        } else {
            logElement.classList.add('system');
        }

        // Aplicar efecto tipowriter
        const span = document.createElement('span');
        this.typeWriter(span, log);
        logElement.appendChild(span);

        return logElement;
    }

    typeWriter(element, text, delay = 20) {
        let i = 0;
        element.textContent = '';
        const cursor = document.createElement('span');
        cursor.className = 'typewriter-cursor';
        element.appendChild(cursor);

        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(type, delay);
            } else {
                cursor.style.display = 'none';
            }
        }
        type();
    }

    showInfo(message) {
        if (!this.contentDiv) return;

        const infoElement = document.createElement('div');
        infoElement.className = 'black-box-log-entry info';
        infoElement.textContent = message;
        this.contentDiv.appendChild(infoElement);
    }

    showError(message) {
        if (!this.contentDiv) return;

        const errorElement = document.createElement('div');
        errorElement.className = 'black-box-log-entry error';
        errorElement.textContent = message;
        this.contentDiv.appendChild(errorElement);
    }

    startPolling() {
        if (!this.pollingActive) {
            this.pollingActive = true;
            this.pollingIntervalId = setInterval(() => {
                if (this.terminal && this.terminal.style.display !== 'none') {
                    this.loadLogs();
                }
            }, this.pollingInterval);
        }
    }

    stopPolling() {
        if (this.pollingActive) {
            clearInterval(this.pollingIntervalId);
            this.pollingActive = false;
        }
    }
}

// Inicializar la Caja Negra cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si los elementos existen antes de inicializar
    if (document.getElementById('blackBoxTerminal') &&
        document.getElementById('blackBoxToggle') &&
        document.querySelectorAll('.black-box-tab').length > 0) {
        const blackBox = new BlackBox();
        console.log('BlackBox inicializado correctamente');
    }
});