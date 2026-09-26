/*
JavaScript para el nuevo dashboard táctico.
Incluye gráficos de radar, barras de recursos, consola interactiva y optimización de rendimiento.
*/

// Configuración global
const tacticalDashboard = {
    // Configuración del radar de amenazas
    threatRadar: {
        canvas: null,
        ctx: null,
        data: {
            critical: 0,
            high: 0,
            medium: 0,
            low: 0
        },
        fps: 60,
        animationFrameId: null,
        isHighPerformance: true,
        init: function() {
            this.canvas = document.getElementById('threatRadarChart');
            this.ctx = this.canvas.getContext('2d');
            this.drawRadar();
            this.updateRadar();
        },
        drawRadar: function() {
            const ctx = this.ctx;
            const centerX = this.canvas.width / 2;
            const centerY = this.canvas.height / 2;
            const radius = Math.min(this.canvas.width, this.canvas.height) * 0.4;

            // Limpiar el canvas
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            // Dibujar el círculo exterior
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(0, 255, 255, 0.2)';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Dibujar las secciones del radar
            const sections = [
                { angle: 0, color: '#ff0000', value: this.data.critical },
                { angle: 90, color: '#ffcc00', value: this.data.high },
                { angle: 180, color: '#00ff00', value: this.data.medium },
                { angle: 270, color: '#0000ff', value: this.data.low }
            ];

            // Dibujar las secciones
            sections.forEach((section, index) => {
                const startAngle = (index * 90) * Math.PI / 180;
                const endAngle = ((index + 1) * 90) * Math.PI / 180;

                // Dibujar el sector
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(
                    centerX + Math.cos(startAngle) * radius,
                    centerY + Math.sin(startAngle) * radius
                );
                ctx.arc(centerX, centerY, radius, startAngle, endAngle, false);
                ctx.closePath();

                // Gradiente para el sector
                const gradient = ctx.createRadialGradient(
                    centerX, centerY, 0,
                    centerX, centerY, radius
                );
                gradient.addColorStop(0, section.color);
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0.3)');
                ctx.fillStyle = gradient;
                ctx.fill();

                // Dibujar el borde del sector
                ctx.strokeStyle = section.color;
                ctx.lineWidth = 2;
                ctx.stroke();

                // Dibujar el valor en el centro
                const textRadius = radius * 0.7;
                const textAngle = startAngle + (endAngle - startAngle) / 2;
                const textX = centerX + Math.cos(textAngle) * textRadius;
                const textY = centerY + Math.sin(textAngle) * textRadius;

                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(section.value, textX, textY);
            });

            // Dibujar el centro
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius * 0.1, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 255, 255, 0.5)';
            ctx.fill();
        },
        updateRadar: function() {
            // Simular datos aleatorios para el radar
            this.data.critical = Math.min(10, this.data.critical + (Math.random() > 0.7 ? 1 : 0));
            this.data.high = Math.min(15, this.data.high + (Math.random() > 0.5 ? 1 : 0));
            this.data.medium = Math.min(20, this.data.medium + (Math.random() > 0.3 ? 1 : 0));
            this.data.low = Math.min(25, this.data.low + (Math.random() > 0.2 ? 1 : 0));

            // Actualizar el gráfico
            this.drawRadar();

            // Actualizar cada X milisegundos según el FPS
            const delay = this.isHighPerformance ? 1000 / this.fps : 1000 / 30;
            this.animationFrameId = setTimeout(() => this.updateRadar(), delay);
        },
        reduceFPS: function() {
            this.fps = 30;
            this.isHighPerformance = false;
            console.log('🔄 Reduciendo FPS a 30 para ahorrar recursos');
        },
        restoreFPS: function() {
            this.fps = 60;
            this.isHighPerformance = true;
            console.log('⚡ Restaurando FPS a 60');
        }
    },

    // Configuración de las barras de recursos
    resourceBars: {
        cpu: {
            element: document.getElementById('cpuFill'),
            valueElement: document.getElementById('cpuValue'),
            update: function(value) {
                this.element.style.width = value + '%';
                this.valueElement.textContent = value + '%';
            }
        },
        ram: {
            element: document.getElementById('ramFill'),
            valueElement: document.getElementById('ramValue'),
            update: function(value) {
                this.element.style.width = value + '%';
                this.valueElement.textContent = value + '%';
            }
        },
        bandwidth: {
            element: document.getElementById('bandwidthFill'),
            valueElement: document.getElementById('bandwidthValue'),
            update: function(value) {
                this.element.style.width = value + '%';
                this.valueElement.textContent = value + '%';
            }
        },
        init: function() {
            // Simular datos aleatorios para las barras
            this.updateResources();
        },
        updateResources: function() {
            const cpuValue = Math.floor(Math.random() * 80) + 10;
            const ramValue = Math.floor(Math.random() * 70) + 20;
            const bandwidthValue = Math.floor(Math.random() * 60) + 15;

            this.cpu.update(cpuValue);
            this.ram.update(ramValue);
            this.bandwidth.update(bandwidthValue);

            // Actualizar cada 3 segundos
            setTimeout(() => this.updateResources(), 3000);
        }
    },

    // Configuración del estado de red
    networkStatus: {
        connectionStatus: document.getElementById('connectionStatus'),
        connectionValue: document.getElementById('connectionValue'),
        latencyValue: document.getElementById('latencyValue'),
        tunnelStatus: document.getElementById('tunnelStatus'),
        tunnelValue: document.getElementById('tunnelValue'),
        init: function() {
            this.updateNetworkStatus();
        },
        updateNetworkStatus: function() {
            // Simular estado de conexión
            const isOnline = Math.random() > 0.1;
            this.connectionStatus.className = isOnline ? 'network-status-indicator online' : 'network-status-indicator offline';
            this.connectionValue.textContent = isOnline ? 'Conectado' : 'Desconectado';

            // Simular latencia
            const latency = Math.floor(Math.random() * 100) + 10;
            this.latencyValue.textContent = latency + ' ms';

            // Simular estado del túnel
            const isTunnelOnline = Math.random() > 0.2;
            this.tunnelStatus.className = isTunnelOnline ? 'network-status-indicator online' : 'network-status-indicator offline';
            this.tunnelValue.textContent = isTunnelOnline ? 'Conectado' : 'Desconectado';

            // Actualizar cada 5 segundos
            setTimeout(() => this.updateNetworkStatus(), 5000);
        }
    },

    // Configuración de la consola táctica
    console: {
        outputElement: document.getElementById('consoleOutput'),
        inputElement: document.querySelector('.console-input'),
        submitElement: document.querySelector('.console-submit'),
        init: function() {
            this.loadInitialLogs();
            this.setupEventListeners();
        },
        loadInitialLogs: function() {
            // Cargar logs iniciales
            const logs = [
                { type: 'info', message: '📡 AURA Tactical Console iniciada' },
                { type: 'info', message: '🔍 Escaneando entorno...' },
                { type: 'info', message: '🌐 Conexión establecida con el núcleo' },
                { type: 'warning', message: '⚠️ 3 alertas pendientes en el ticker' },
                { type: 'info', message: '📊 Radar de amenazas actualizado' }
            ];

            this.outputElement.innerHTML = logs.map(log =>
                `<div class="log-line ${log.type}">${log.message}</div>`
            ).join('');
            this.scrollToBottom();
        },
        setupEventListeners: function() {
            // Enviar comando al presionar Enter
            this.inputElement.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.submitCommand();
                }
            });

            // Enviar comando al hacer clic en el botón
            this.submitElement.addEventListener('click', () => {
                this.submitCommand();
            });
        },
        submitCommand: function() {
            const command = this.inputElement.value.trim();
            if (command) {
                // Añadir el comando al historial
                this.addLog('info', `> ${command}`);

                // Simular respuesta del sistema
                setTimeout(() => {
                    if (command.toLowerCase() === 'status') {
                        this.addLog('info', '📡 Sistema operativo: AURA v2.7.1');
                        this.addLog('info', '🖥️ Modo: Stealth');
                        this.addLog('info', '🔒 Estado: Activo');
                    } else if (command.toLowerCase() === 'threat') {
                        this.addLog('warning', '⚠️ Amenazas detectadas: 3 (1 crítica)');
                    } else if (command.toLowerCase() === 'clear') {
                        this.outputElement.innerHTML = '';
                    } else {
                        this.addLog('info', `💡 Comando "${command}" no reconocido. Usa "status" o "threat".`);
                    }
                }, 500);

                // Limpiar el input
                this.inputElement.value = '';
            }
        },
        addLog: function(type, message) {
            const logElement = document.createElement('div');
            logElement.className = `log-line ${type}`;
            logElement.textContent = message;
            this.outputElement.appendChild(logElement);
            this.scrollToBottom();
        },
        scrollToBottom: function() {
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        }
    },

    // Inicializar el dashboard táctico cuando la página esté cargada
    init: function() {
        // Inicializar los componentes
        this.threatRadar.init();
        this.resourceBars.init();
        this.networkStatus.init();
        this.console.init();

        // Cargar datos dinámicos desde el backend
        this.loadDynamicData();

        // Inicializar el módulo de UI inmersiva
        if (typeof immersiveUI !== 'undefined') {
            immersiveUI.init();
        }
    },

    // Cargar datos dinámicos desde el backend
    loadDynamicData: function() {
        // Actualizar datos del radar
        setInterval(() => {
            fetch('/api/tactical/world_state')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ok') {
                        const threatScore = data.world_state.threat_score || 0;
                        tacticalDashboard.threatRadar.data.critical = Math.min(10, threatScore / 10);
                        tacticalDashboard.threatRadar.drawRadar();
                    }
                })
                .catch(error => {
                    console.error('Error cargando datos del radar:', error);
                });

            // Actualizar recursos
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    if (data.cpu_percent) {
                        tacticalDashboard.resourceBars.cpu.update(Math.min(90, data.cpu_percent));
                    }
                    if (data.ram_free_gb && data.ram_total_gb) {
                        const ramUsed = ((data.ram_total_gb - data.ram_free_gb) / data.ram_total_gb) * 100;
                        tacticalDashboard.resourceBars.ram.update(Math.min(90, ramUsed));
                    }
                })
                .catch(error => {
                    console.error('Error cargando datos de recursos:', error);
                });
        }, 5000);
    }
};

// Inicializar el dashboard táctico cuando la página esté cargada
document.addEventListener('DOMContentLoaded', function() {
    tacticalDashboard.init();
});