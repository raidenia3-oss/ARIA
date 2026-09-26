/*
 * telemetry_dashboard.js - Frontend para el dashboard de telemetría de AURA.
 * Este script se encarga de conectarse al servidor WebSocket para recibir datos de telemetría
 * en tiempo real y mostrar tarjetas de estado en el dashboard.
 */

// Configuración global
const TELEMETRY_WS_URL = "ws://localhost:8765";
const TELEMETRY_HISTORY_URL = "/api/telemetry/history";

// Variables globales
let telemetryWebSocket = null;
let telemetryData = {};
let activeDevices = {};
let telemetryHistory = [];

// DOM Elements
const connectionStatusElement = document.getElementById('connection-status');
const cpuUsageElement = document.getElementById('cpu-usage');
const temperatureElement = document.getElementById('temperature');
const batteryLevelElement = document.getElementById('battery-level');
const activeNodesElement = document.getElementById('active-nodes');
const telemetryHistoryContainer = document.getElementById('telemetry-history');

// Inicialización del dashboard
function initDashboard() {
    // Conectar al servidor WebSocket
    connectWebSocket();

    // Cargar historial de telemetría
    loadTelemetryHistory();

    // Actualizar el estado de conexión
    updateConnectionStatus("Desconectado");

    // Configurar eventos para las tarjetas
    setupCardEvents();
}

// Conectar al servidor WebSocket
function connectWebSocket() {
    telemetryWebSocket = new WebSocket(TELEMETRY_WS_URL);

    telemetryWebSocket.onopen = function() {
        updateConnectionStatus("Conectado");
        console.log("Conectado al servidor de telemetría.");
    };

    telemetryWebSocket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            processTelemetryData(data);
        } catch (e) {
            console.error("Error al procesar datos de telemetría:", e);
        }
    };

    telemetryWebSocket.onclose = function() {
        updateConnectionStatus("Desconectado");
        console.log("Desconectado del servidor de telemetría.");
        // Reintentar conexión después de 5 segundos
        setTimeout(connectWebSocket, 5000);
    };

    telemetryWebSocket.onerror = function(error) {
        console.error("Error en la conexión WebSocket:", error);
    };
}

// Actualizar el estado de conexión
function updateConnectionStatus(status) {
    connectionStatusElement.textContent = status;
    connectionStatusElement.className = status === "Conectado" ? "status-connected" : "status-disconnected";
}

// Procesar datos de telemetría recibidos
function processTelemetryData(data) {
    const deviceId = data.device_id;
    const timestamp = data.timestamp;
    const telemetry = data.data;

    // Actualizar datos del dispositivo
    if (!activeDevices[deviceId]) {
        activeDevices[deviceId] = {
            lastUpdate: timestamp,
            data: {}
        };
    }

    activeDevices[deviceId].lastUpdate = timestamp;
    activeDevices[deviceId].data = telemetry;

    // Actualizar tarjetas de estado
    updateDashboardCards();

    // Guardar en el historial
    telemetryData[deviceId] = telemetryData[deviceId] || [];
    telemetryData[deviceId].push({
        timestamp: timestamp,
        data: telemetry
    });

    // Limitar el tamaño del historial en memoria
    if (telemetryData[deviceId].length > 100) {
        telemetryData[deviceId] = telemetryData[deviceId].slice(-100);
    }

    // Actualizar el historial visual
    updateTelemetryHistory();
}

// Actualizar las tarjetas del dashboard
function updateDashboardCards() {
    // Contar nodos activos
    const activeNodeCount = Object.keys(activeDevices).length;
    activeNodesElement.textContent = activeNodeCount;

    // Obtener el último dispositivo activo (para mostrar datos)
    const lastDeviceId = Object.keys(activeDevices).pop();
    if (lastDeviceId && activeDevices[lastDeviceId].data) {
        const deviceData = activeDevices[lastDeviceId].data;

        // Actualizar tarjetas
        if (deviceData.connection_status) {
            const status = deviceData.connection_status === "active" ? "Conectado" : "Desconectado";
            connectionStatusElement.textContent = status;
            connectionStatusElement.className = status === "Conectado" ? "status-connected" : "status-disconnected";
        }

        if (deviceData.cpu_usage !== undefined) {
            cpuUsageElement.textContent = `${deviceData.cpu_usage.toFixed(1)}%`;
            cpuUsageElement.className = deviceData.cpu_usage > 80 ? "high" : "normal";
        }

        if (deviceData.temperature !== undefined) {
            temperatureElement.textContent = `${deviceData.temperature.toFixed(1)}°C`;
            temperatureElement.className = deviceData.temperature > 40 ? "high" : "normal";
        }

        if (deviceData.battery_level !== undefined) {
            batteryLevelElement.textContent = `${deviceData.battery_level}%`;
            batteryLevelElement.className = deviceData.battery_level < 20 ? "low" : "normal";
        }
    }
}

// Cargar historial de telemetría desde el backend
function loadTelemetryHistory() {
    fetch(TELEMETRY_HISTORY_URL)
        .then(response => response.json())
        .then(data => {
            telemetryHistory = data;
            updateTelemetryHistory();
        })
        .catch(error => {
            console.error("Error al cargar el historial de telemetría:", error);
        });
}

// Actualizar la visualización del historial de telemetría
function updateTelemetryHistory() {
    telemetryHistoryContainer.innerHTML = "";

    // Mostrar los últimos 10 registros del historial
    const historyToShow = telemetryHistory.slice(-10).reverse();

    historyToShow.forEach(entry => {
        const deviceId = entry.device_id;
        const timestamp = new Date(entry.timestamp).toLocaleString();
        const data = entry.data;

        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';

        const status = data.connection_status || "Desconectado";
        const statusClass = status === "active" ? "status-connected" : "status-disconnected";

        historyItem.innerHTML = `
            <div class="history-timestamp">${timestamp}</div>
            <div class="history-device">${deviceId}</div>
            <div class="history-status ${statusClass}">${status}</div>
            <div class="history-details">
                <div>CPU: ${data.cpu_usage ? `${data.cpu_usage.toFixed(1)}%` : "N/A"}</div>
                <div>Temp: ${data.temperature ? `${data.temperature.toFixed(1)}°C` : "N/A"}</div>
                <div>Batería: ${data.battery_level ? `${data.battery_level}%` : "N/A"}</div>
            </div>
        `;

        telemetryHistoryContainer.appendChild(historyItem);
    });
}

// Configurar eventos para las tarjetas
function setupCardEvents() {
    // Eventos para las tarjetas (ej: hover, click)
    document.querySelectorAll('.telemetry-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
}

// Iniciar el dashboard cuando el DOM esté cargado
document.addEventListener('DOMContentLoaded', initDashboard);