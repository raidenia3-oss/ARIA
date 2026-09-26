/*
Telemetry Dashboard para AURA.
Muestra métricas de rendimiento en tiempo real usando gráficos de Chart.js.
*/

// Configuración global
const telemetryDashboard = {
    socket: null,
    charts: {},
    updateInterval: 2000, // Actualizar cada 2 segundos

    // Inicializar el dashboard de telemetría
    init: function() {
        this.setupSocketConnection();
        this.createTelemetryTab();
        this.setupCharts();
        this.startUpdates();
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
                console.log('🔗 Conectado al servidor de telemetría');
            });

            this.socket.on('disconnect', () => {
                console.log('🔘 Desconectado del servidor de telemetría');
            });
        }
    },

    // Crear pestaña de telemetría en el dashboard
    createTelemetryTab: function() {
        // Crear contenedor para la pestaña de telemetría
        const telemetryTab = document.createElement('div');
        telemetryTab.id = 'telemetryTab';
        telemetryTab.className = 'telemetry-tab';
        telemetryTab.style.display = 'none';
        telemetryTab.style.padding = '20px';
        telemetryTab.style.backgroundColor = 'rgba(0, 0, 0, 0.3)';
        telemetryTab.style.borderRadius = '10px';
        telemetryTab.style.margin = '20px';

        // Crear título de la pestaña
        const title = document.createElement('h2');
        title.textContent = '📊 Telemetría del Sistema';
        title.style.color = '#00ff00';
        title.style.marginTop = '0';

        // Crear contenedor para los gráficos
        const chartsContainer = document.createElement('div');
        chartsContainer.className = 'telemetry-charts-container';
        chartsContainer.style.display = 'flex';
        chartsContainer.style.flexWrap = 'wrap';
        chartsContainer.style.gap = '20px';

        // Añadir contenedores para cada gráfico
        const cpuChartContainer = document.createElement('div');
        cpuChartContainer.className = 'telemetry-chart';
        cpuChartContainer.style.flex = '1 1 300px';
        cpuChartContainer.style.minWidth = '300px';

        const memoryChartContainer = document.createElement('div');
        memoryChartContainer.className = 'telemetry-chart';
        memoryChartContainer.style.flex = '1 1 300px';
        memoryChartContainer.style.minWidth = '300px';

        const gpuChartContainer = document.createElement('div');
        gpuChartContainer.className = 'telemetry-chart';
        gpuChartContainer.style.flex = '1 1 300px';
        gpuChartContainer.style.minWidth = '300px';

        const diskChartContainer = document.createElement('div');
        diskChartContainer.className = 'telemetry-chart';
        diskChartContainer.style.flex = '1 1 300px';
        diskChartContainer.style.minWidth = '300px';

        const networkChartContainer = document.createElement('div');
        networkChartContainer.className = 'telemetry-chart';
        networkChartContainer.style.flex = '1 1 300px';
        networkChartContainer.style.minWidth = '300px';

        const ollamaLatencyChartContainer = document.createElement('div');
        ollamaLatencyChartContainer.className = 'telemetry-chart';
        ollamaLatencyChartContainer.style.flex = '1 1 300px';
        ollamaLatencyChartContainer.style.minWidth = '300px';

        const shadowCoreLatencyChartContainer = document.createElement('div');
        shadowCoreLatencyChartContainer.className = 'telemetry-chart';
        shadowCoreLatencyChartContainer.style.flex = '1 1 300px';
        shadowCoreLatencyChartContainer.style.minWidth = '300px';

        // Añadir los contenedores al dashboard
        chartsContainer.appendChild(cpuChartContainer);
        chartsContainer.appendChild(memoryChartContainer);
        chartsContainer.appendChild(gpuChartContainer);
        chartsContainer.appendChild(diskChartContainer);
        chartsContainer.appendChild(networkChartContainer);
        chartsContainer.appendChild(ollamaLatencyChartContainer);
        chartsContainer.appendChild(shadowCoreLatencyChartContainer);

        // Añadir título y contenedor de gráficos al tab
        telemetryTab.appendChild(title);
        telemetryTab.appendChild(chartsContainer);

        // Añadir la pestaña al dashboard
        document.body.appendChild(telemetryTab);

        // Guardar referencias a los contenedores de gráficos
        this.charts = {
            cpu: cpuChartContainer,
            memory: memoryChartContainer,
            gpu: gpuChartContainer,
            disk: diskChartContainer,
            network: networkChartContainer,
            ollamaLatency: ollamaLatencyChartContainer,
            shadowCoreLatency: shadowCoreLatencyChartContainer
        };

        // Mostrar la pestaña de telemetría
        telemetryTab.style.display = 'block';
    },

    // Configurar los gráficos
    setupCharts: function() {
        // Configuración base para todos los gráficos
        const config = {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.2)'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    }
                },
                animation: {
                    duration: 1000
                }
            }
        };

        // Crear gráficos para cada métrica
        for (const chartName in this.charts) {
            const chartContainer = this.charts[chartName];
            const chartConfig = JSON.parse(JSON.stringify(config));

            // Configurar datos específicos para cada gráfico
            if (chartName === 'cpu') {
                chartConfig.data.datasets = [{
                    label: 'Uso de CPU (%)',
                    borderColor: '#00ff00',
                    backgroundColor: 'rgba(0, 255, 0, 0.1)',
                    data: [],
                    fill: true
                }];
            } else if (chartName === 'memory') {
                chartConfig.data.datasets = [{
                    label: 'Uso de Memoria (MB)',
                    borderColor: '#00aaff',
                    backgroundColor: 'rgba(0, 170, 255, 0.1)',
                    data: [],
                    fill: true
                }];
            } else if (chartName === 'gpu') {
                chartConfig.data.datasets = [{
                    label: 'Uso de GPU (%)',
                    borderColor: '#ff00ff',
                    backgroundColor: 'rgba(255, 0, 255, 0.1)',
                    data: [],
                    fill: true
                }];
            } else if (chartName === 'disk') {
                chartConfig.data.datasets = [{
                    label: 'Uso de Disco (%)',
                    borderColor: '#ffff00',
                    backgroundColor: 'rgba(255, 255, 0, 0.1)',
                    data: [],
                    fill: true
                }];
            } else if (chartName === 'network') {
                chartConfig.data.datasets = [{
                    label: 'Tráfico de Red (KB/s)',
                    borderColor: '#ff8800',
                    backgroundColor: 'rgba(255, 136, 0, 0.1)',
                    data: [],
                    fill: true
                }];
            } else if (chartName === 'ollamaLatency') {
                chartConfig.data.datasets = [{
                    label: 'Latencia de Ollama (ms)',
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    data: [],
                    fill: false
                }];
            } else if (chartName === 'shadowCoreLatency') {
                chartConfig.data.datasets = [{
                    label: 'Latencia de Shadow Core (ms)',
                    borderColor: '#ff0088',
                    backgroundColor: 'rgba(255, 0, 136, 0.1)',
                    data: [],
                    fill: false
                }];
            }

            // Crear el gráfico
            const ctx = chartContainer.getContext('2d');
            this.charts[chartName].chart = new Chart(ctx, chartConfig);
        }
    },

    // Iniciar actualizaciones de métricas
    startUpdates: function() {
        setInterval(() => {
            this.fetchTelemetryData();
        }, this.updateInterval);
    },

    // Obtener datos de telemetría
    fetchTelemetryData: function() {
        fetch('/api/telemetry/system')
            .then(response => response.json())
            .then(data => {
                this.updateCharts(data);
            })
            .catch(error => {
                console.error('Error al obtener datos de telemetría:', error);
            });
    },

    // Actualizar gráficos con nuevos datos
    updateCharts: function(data) {
        const timestamp = new Date().toLocaleTimeString();

        // Actualizar datos de CPU
        this.updateChartData('cpu', data.cpu_usage, timestamp);

        // Actualizar datos de Memoria (convertir a MB)
        const memoryUsageMB = data.memory_usage / (1024 * 1024);
        this.updateChartData('memory', memoryUsageMB, timestamp);

        // Actualizar datos de GPU
        this.updateChartData('gpu', data.gpu_usage, timestamp);

        // Actualizar datos de Disco
        this.updateChartData('disk', data.disk_usage, timestamp);

        // Actualizar datos de Red (convertir a KB/s)
        const networkIOKB = (data.network_io / 1024) / 1024; // Convertir a KB/s
        this.updateChartData('network', networkIOKB, timestamp);

        // Actualizar datos de Latencia de Ollama (convertir a ms)
        const ollamaLatencyMS = data.ollama.latency * 1000;
        this.updateChartData('ollamaLatency', ollamaLatencyMS, timestamp);

        // Actualizar datos de Latencia de Shadow Core (convertir a ms)
        const shadowCoreLatencyMS = data.shadow_core.latency * 1000;
        this.updateChartData('shadowCoreLatency', shadowCoreLatencyMS, timestamp);
    },

    // Actualizar datos de un gráfico específico
    updateChartData: function(chartName, value, timestamp) {
        const chart = this.charts[chartName].chart;
        const dataset = chart.data.datasets[0];

        // Añadir nuevo dato
        dataset.data.push(value);

        // Limitar el número de datos para evitar que el gráfico se vuelva demasiado grande
        if (dataset.data.length > 60) {
            dataset.data.shift();
            chart.data.labels.shift();
        }

        // Añadir etiqueta de tiempo
        chart.data.labels.push(timestamp);

        // Actualizar el gráfico
        chart.update();
    }
};

// Inicializar el dashboard de telemetría cuando la página esté cargada
document.addEventListener('DOMContentLoaded', function() {
    // Cargar Chart.js
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.onload = function() {
        telemetryDashboard.init();
    };
    document.head.appendChild(script);
});