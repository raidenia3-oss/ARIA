/**
 * Módulo de Radar de Reconocimiento Pasivo Unificado para AME.
 * Combina identificación de redes y análisis de presencia en una sola interfaz.
 */

// Configuración de la API
const RADAR_API_URL = 'http://localhost:5000/api/radar';
const MASTER_API_KEY = 'AURA_MASTER_KEY_2026';
const DEFAULT_THRESHOLD = 60; // Umbral en dB (conversación normal)
const SCAN_INTERVAL = 10000; // 10 segundos entre escaneos
const PRESENCE_THRESHOLD = 15; // Umbral de diferencia de RSSI para detectar perturbación

// Variables globales para el estado del radar
let radarActive = false;
let scanIntervalId = null;
let lastScanTime = null;
let presenceAlerts = [];
let radarHistory = [];
let currentTab = 'identification'; // 'identification' o 'presence'

// Función para solicitar permisos de ubicación
async function requestLocationPermission() {
    return new Promise((resolve) => {
        if (!navigator.permissions) {
            resolve(true);
            return;
        }

        navigator.permissions.query({ name: 'geolocation' }).then((permissionStatus) => {
            if (permissionStatus.state === 'granted' || permissionStatus.state === 'prompt') {
                resolve(true);
            } else {
                // Solicitar permiso al usuario
                navigator.geolocation.getCurrentPosition(
                    () => resolve(true),
                    () => resolve(false),
                    { enableHighAccuracy: true }
                );
            }
        });
    });
}

// Función para escanear redes WiFi (simulada para Capacitor)
async function scanWiFiNetworks() {
    return new Promise(async (resolve) => {
        try {
            // Solicitar permisos de ubicación
            const hasPermission = await requestLocationPermission();
            if (!hasPermission) {
                throw new Error('Permiso de ubicación denegado');
            }

            // Simulación de escaneo de redes WiFi (en un entorno real, esto usaría Capacitor)
            // En un entorno real, usaríamos el plugin @capacitor/community/wifi
            // o un plugin personalizado para Android/iOS

            // Simular una lista de redes WiFi cercanas con información enriquecida
            const simulatedNetworks = [
                {
                    ssid: "AURA-Home",
                    bssid: "A4:B1:D4:E2:F3:56",
                    rssi: -65,
                    timestamp: new Date().toISOString(),
                    manufacturer: "Apple, Inc.",
                    device_type: "Router/Point de acceso"
                },
                {
                    ssid: "CaféWiFi",
                    bssid: "B8:27:EB:3D:4E:F1",
                    rssi: -72,
                    timestamp: new Date().toISOString(),
                    manufacturer: "TP-Link Technologies Co., Ltd.",
                    device_type: "Router/Point de acceso"
                },
                {
                    ssid: "GalaxyS23",
                    bssid: "00:1E:C2:1F:33:44",
                    rssi: -68,
                    timestamp: new Date().toISOString(),
                    manufacturer: "Samsung Electronics Co., Ltd",
                    device_type: "Smartphone Samsung"
                },
                {
                    ssid: "MiPhone12",
                    bssid: "00:18:F3:12:34:56",
                    rssi: -75,
                    timestamp: new Date().toISOString(),
                    manufacturer: "Xiaomi Inc.",
                    device_type: "Smartphone Xiaomi"
                },
                {
                    ssid: "OfficeNetwork",
                    bssid: "3C:4A:96:1B:2D:E4",
                    rssi: -80,
                    timestamp: new Date().toISOString(),
                    manufacturer: "Huawei Technologies Co., Ltd",
                    device_type: "Router/Point de acceso"
                }
            ];

            // En un entorno real, esto sería reemplazado por:
            // const networks = await Capacitor.WiFi.scan();
            // return networks.map(network => ({
            //     ssid: network.SSID,
            //     bssid: network.BSSID,
            //     rssi: network.RSSI,
            //     timestamp: new Date().toISOString()
            // }));

            resolve(simulatedNetworks);
        } catch (error) {
            console.error('Error al escanear redes WiFi:', error);
            resolve([]);
        }
    });
}

// Función para enviar los datos del escaneo a AURA
async function sendScanToAura(networks) {
    try {
        const response = await fetch(RADAR_API_URL + '/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': MASTER_API_KEY
            },
            body: JSON.stringify({
                networks: networks,
                timestamp: new Date().toISOString()
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Error al enviar datos al servidor');
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error al enviar datos a AURA:', error);
        throw error;
    }
}

// Función para obtener el historial de escaneos desde AURA
async function getRadarHistory(limit = 20) {
    try {
        const response = await fetch(RADAR_API_URL + '/history?limit=' + limit, {
            headers: {
                'X-API-KEY': MASTER_API_KEY
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Error al obtener historial del servidor');
        }

        const data = await response.json();
        return data.results || [];
    } catch (error) {
        console.error('Error al obtener historial de escaneos:', error);
        return [];
    }
}

// Función para obtener el análisis de presencia desde AURA
async function getPresenceAnalysis(limit = 10) {
    try {
        const response = await fetch(RADAR_API_URL + '/presence?limit=' + limit, {
            headers: {
                'X-API-KEY': MASTER_API_KEY
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Error al obtener análisis de presencia');
        }

        const data = await response.json();
        return data.results || [];
    } catch (error) {
        console.error('Error al obtener análisis de presencia:', error);
        return [];
    }
}

// Función para mostrar los resultados del escaneo en el dashboard
function displayScanResults(networks) {
    const radarResultsDiv = document.getElementById('radar-networks-list');
    if (!radarResultsDiv) return;

    radarResultsDiv.innerHTML = '';

    if (networks.length === 0) {
        radarResultsDiv.innerHTML = '<div class="no-networks">No se encontraron redes WiFi cercanas.</div>';
        return;
    }

    // Crear una lista de redes encontradas
    const list = document.createElement('ul');
    list.style.listStyle = 'none';
    list.style.padding = '0';
    list.style.margin = '0';

    networks.forEach(network => {
        const item = document.createElement('li');
        item.style.padding = '12px 0';
        item.style.borderBottom = '1px solid var(--border-color)';
        item.style.display = 'flex';
        item.style.justifyContent = 'space-between';
        item.style.color = 'var(--text-primary)';
        item.style.transition = 'all 0.3s ease';

        // Determinar el color basado en el tipo de dispositivo
        let deviceColor = 'var(--text-secondary)';
        if (network.device_type.includes('Smartphone') || network.device_type.includes('Dispositivo móvil')) {
            deviceColor = 'var(--accent-color)';
        } else if (network.device_type.includes('Router') || network.device_type.includes('Point de acceso')) {
            deviceColor = 'var(--accent-secondary)';
        }

        // Crear elementos para la red
        const ssidElement = document.createElement('div');
        ssidElement.style.display = 'flex';
        ssidElement.style.flexDirection = 'column';
        ssidElement.style.flex = '1';

        const ssidTitle = document.createElement('div');
        ssidTitle.textContent = network.ssid;
        ssidTitle.style.fontWeight = 'bold';
        ssidTitle.style.marginBottom = '4px';

        const ssidDetails = document.createElement('div');
        ssidDetails.style.display = 'flex';
        ssidDetails.style.flexWrap = 'wrap';
        ssidDetails.style.gap = '8px';
        ssidDetails.style.fontSize = '0.8rem';
        ssidDetails.style.color = 'var(--text-secondary)';

        const manufacturerSpan = document.createElement('span');
        manufacturerSpan.textContent = network.manufacturer;
        manufacturerSpan.style.color = deviceColor;

        const deviceTypeSpan = document.createElement('span');
        deviceTypeSpan.textContent = network.device_type;

        const rssiSpan = document.createElement('span');
        rssiSpan.textContent = `${network.rssi} dBm`;
        rssiSpan.style.fontWeight = 'bold';

        ssidDetails.appendChild(manufacturerSpan);
        ssidDetails.appendChild(document.createTextNode(' | '));
        ssidDetails.appendChild(deviceTypeSpan);
        ssidDetails.appendChild(document.createTextNode(' | '));
        ssidDetails.appendChild(rssiSpan);

        ssidElement.appendChild(ssidTitle);
        ssidElement.appendChild(ssidDetails);

        // Crear el gráfico de señal
        const signalGraph = document.createElement('div');
        signalGraph.style.width = '80px';
        signalGraph.style.height = '20px';
        signalGraph.style.display = 'flex';
        signalGraph.style.alignItems = 'center';
        signalGraph.style.justifyContent = 'flex-end';

        const signalBar = document.createElement('div');
        signalBar.style.width = `${Math.min(80, 80 + network.rssi)}px`;
        signalBar.style.height = '100%';
        signalBar.style.backgroundColor = getSignalColor(network.rssi);
        signalBar.style.borderRadius = '2px 0 0 2px';

        signalGraph.appendChild(signalBar);

        // Crear el BSSID (oculto por defecto)
        const bssidElement = document.createElement('div');
        bssidElement.textContent = network.bssid;
        bssidElement.style.fontSize = '0.7rem';
        bssidElement.style.color = 'var(--text-tertiary)';
        bssidElement.style.cursor = 'pointer';
        bssidElement.style.marginLeft = '8px';
        bssidElement.style.display = 'none';

        // Evento para mostrar/ocultar BSSID
        ssidElement.addEventListener('click', () => {
            if (bssidElement.style.display === 'none') {
                bssidElement.style.display = 'block';
            } else {
                bssidElement.style.display = 'none';
            }
        });

        // Agregar todos los elementos al item
        item.appendChild(ssidElement);
        item.appendChild(signalGraph);
        item.appendChild(bssidElement);

        list.appendChild(item);
    });

    radarResultsDiv.appendChild(list);

    // Actualizar el gráfico de redes detectadas
    updateNetworkMapVisualization(networks);
}

// Función para obtener el color basado en la fuerza de señal
function getSignalColor(rssi) {
    // Convertir RSSI a un valor entre 0-100 para el gráfico
    const normalizedRssi = Math.min(100, Math.max(0, -rssi));

    // Escala de colores basada en la fuerza de señal
    if (normalizedRssi > 70) return 'var(--signal-strong)';
    if (normalizedRssi > 40) return 'var(--signal-medium)';
    if (normalizedRssi > 20) return 'var(--signal-weak)';
    return 'var(--signal-very-weak)';
}

// Función para mostrar alertas de presencia
function displayPresenceAlerts(alerts) {
    const presenceAlertsDiv = document.getElementById('presence-alerts-list');
    if (!presenceAlertsDiv) return;

    presenceAlertsDiv.innerHTML = '';

    if (alerts.length === 0) {
        presenceAlertsDiv.innerHTML = '<div class="no-alerts">No se han detectado perturbaciones significativas.</div>';
        return;
    }

    // Ordenar alertas por índice de perturbación (de mayor a menor)
    alerts.sort((a, b) => b.perturbation_index - a.perturbation_index);

    const list = document.createElement('ul');
    list.style.listStyle = 'none';
    list.style.padding = '0';
    list.style.margin = '0';

    alerts.forEach(alert => {
        const item = document.createElement('li');
        item.style.padding = '12px 0';
        item.style.borderBottom = '1px solid var(--border-color)';
        item.style.display = 'flex';
        item.style.justifyContent = 'space-between';
        item.style.color = 'var(--text-primary)';
        item.style.backgroundColor = getAlertSeverityColor(alert.perturbation_index);

        // Determinar el color basado en la severidad
        const severityColor = getAlertSeverityColor(alert.perturbation_index);

        // Crear elementos para la alerta
        const alertInfo = document.createElement('div');
        alertInfo.style.display = 'flex';
        alertInfo.style.flexDirection = 'column';
        alertInfo.style.flex = '1';

        const alertTitle = document.createElement('div');
        alertTitle.textContent = `🚨 Perturbación detectada en ${alert.ssid}`;
        alertTitle.style.fontWeight = 'bold';
        alertTitle.style.marginBottom = '4px';

        const alertDetails = document.createElement('div');
        alertDetails.style.display = 'flex';
        alertDetails.style.flexWrap = 'wrap';
        alertDetails.style.gap = '8px';
        alertDetails.style.fontSize = '0.8rem';

        const manufacturerSpan = document.createElement('span');
        manufacturerSpan.textContent = alert.manufacturer;
        manufacturerSpan.style.color = severityColor;

        const deviceTypeSpan = document.createElement('span');
        deviceTypeSpan.textContent = alert.device_type;

        const rssiChangeSpan = document.createElement('span');
        rssiChangeSpan.textContent = `Cambio: ${alert.rssi_initial} → ${alert.rssi_current} dBm`;
        rssiChangeSpan.style.fontWeight = 'bold';

        alertDetails.appendChild(manufacturerSpan);
        alertDetails.appendChild(document.createTextNode(' | '));
        alertDetails.appendChild(deviceTypeSpan);
        alertDetails.appendChild(document.createTextNode(' | '));
        alertDetails.appendChild(rssiChangeSpan);

        alertInfo.appendChild(alertTitle);
        alertInfo.appendChild(alertDetails);

        // Crear barra de severidad
        const severityBar = document.createElement('div');
        severityBar.style.width = '80px';
        severityBar.style.height = '20px';
        severityBar.style.backgroundColor = severityColor;
        severityBar.style.borderRadius = '2px';

        // Crear texto de severidad
        const severityText = document.createElement('div');
        severityText.textContent = `Severidad: ${Math.round(alert.perturbation_index)}%`;
        severityText.style.fontSize = '0.8rem';
        severityText.style.color = 'var(--text-primary)';
        severityText.style.marginLeft = '8px';

        // Agregar todos los elementos al item
        item.appendChild(alertInfo);
        item.appendChild(severityBar);
        item.appendChild(severityText);

        list.appendChild(item);
    });

    presenceAlertsDiv.appendChild(list);
}

// Función para obtener el color basado en la severidad de la alerta
function getAlertSeverityColor(severity) {
    if (severity > 70) return 'var(--alert-critical)';
    if (severity > 40) return 'var(--alert-high)';
    if (severity > 20) return 'var(--alert-medium)';
    return 'var(--alert-low)';
}

// Función para actualizar la visualización del mapa de redes
function updateNetworkMapVisualization(networks) {
    const networkMapDiv = document.getElementById('network-map-visualization');
    if (!networkMapDiv) return;

    // Limpiar el contenedor
    networkMapDiv.innerHTML = '';

    // Crear un contenedor para los círculos
    const circlesContainer = document.createElement('div');
    circlesContainer.style.position = 'relative';
    circlesContainer.style.width = '100%';
    circlesContainer.style.height = '200px';
    circlesContainer.style.display = 'flex';
    circlesContainer.style.justifyContent = 'center';
    circlesContainer.style.alignItems = 'center';
    circlesContainer.style.overflow = 'hidden';
    circlesContainer.style.borderRadius = '8px';
    circlesContainer.style.backgroundColor = 'var(--card-background)';
    circlesContainer.style.border = '1px solid var(--border-color)';
    circlesContainer.style.marginBottom = '16px';

    // Crear un círculo central
    const centerCircle = document.createElement('div');
    centerCircle.style.position = 'absolute';
    centerCircle.style.width = '12px';
    centerCircle.style.height = '12px';
    centerCircle.style.backgroundColor = 'var(--accent-color)';
    centerCircle.style.borderRadius = '50%';
    centerCircle.style.zIndex = '10';
    centerCircle.style.boxShadow = '0 0 0 2px var(--accent-secondary)';

    circlesContainer.appendChild(centerCircle);

    // Posicionar los círculos de redes en un patrón circular
    const centerX = circlesContainer.offsetWidth / 2;
    const centerY = circlesContainer.offsetHeight / 2;
    const maxRadius = Math.min(centerX, centerY) * 0.8;
    const angleStep = (2 * Math.PI) / networks.length;

    networks.forEach((network, index) => {
        // Calcular posición basada en el RSSI (más negativo = más lejos)
        const angle = index * angleStep;
        const distanceFactor = Math.max(0.2, Math.min(0.8, (-network.rssi + 30) / 110));
        const radius = maxRadius * distanceFactor;

        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);

        // Crear círculo para la red
        const networkCircle = document.createElement('div');
        networkCircle.style.position = 'absolute';
        networkCircle.style.left = `${x - 6}px`;
        networkCircle.style.top = `${y - 6}px`;
        networkCircle.style.width = '12px';
        networkCircle.style.height = '12px';
        networkCircle.style.backgroundColor = getSignalColor(network.rssi);
        networkCircle.style.borderRadius = '50%';
        networkCircle.style.zIndex = '1';
        networkCircle.style.boxShadow = '0 0 0 2px rgba(0,0,0,0.1)';
        networkCircle.style.cursor = 'pointer';
        networkCircle.style.transition = 'all 0.3s ease';

        // Agregar tooltip
        networkCircle.title = `${network.ssid} (${network.rssi} dBm) - ${network.manufacturer}`;

        // Evento para mostrar detalles al hacer clic
        networkCircle.addEventListener('click', () => {
            showNetworkDetails(network);
        });

        circlesContainer.appendChild(networkCircle);
    });

    networkMapDiv.appendChild(circlesContainer);

    // Mostrar leyenda
    const legend = document.createElement('div');
    legend.style.display = 'flex';
    legend.style.justifyContent = 'space-between';
    legend.style.marginTop = '8px';
    legend.style.fontSize = '0.8rem';
    legend.style.color = 'var(--text-secondary)';

    // Leyenda de colores
    const colorLegend = document.createElement('div');
    colorLegend.style.display = 'flex';
    colorLegend.style.alignItems = 'center';

    const strongColor = document.createElement('div');
    strongColor.style.width = '12px';
    strongColor.style.height = '12px';
    strongColor.style.backgroundColor = 'var(--signal-strong)';
    strongColor.style.borderRadius = '50%';
    strongColor.style.marginRight = '8px';

    const mediumColor = document.createElement('div');
    mediumColor.style.width = '12px';
    mediumColor.style.height = '12px';
    mediumColor.style.backgroundColor = 'var(--signal-medium)';
    mediumColor.style.borderRadius = '50%';
    mediumColor.style.marginRight = '8px';

    const weakColor = document.createElement('div');
    weakColor.style.width = '12px';
    weakColor.style.height = '12px';
    weakColor.style.backgroundColor = 'var(--signal-weak)';
    weakColor.style.borderRadius = '50%';
    weakColor.style.marginRight = '8px';

    const veryWeakColor = document.createElement('div');
    veryWeakColor.style.width = '12px';
    veryWeakColor.style.height = '12px';
    veryWeakColor.style.backgroundColor = 'var(--signal-very-weak)';
    veryWeakColor.style.borderRadius = '50%';
    veryWeakColor.style.marginRight = '8px';

    const strongLabel = document.createElement('span');
    strongLabel.textContent = 'Fuerte';

    const weakLabel = document.createElement('span');
    weakLabel.textContent = 'Débil';

    colorLegend.appendChild(strongColor);
    colorLegend.appendChild(strongLabel);
    colorLegend.appendChild(document.createTextNode(' → '));
    colorLegend.appendChild(mediumColor);
    colorLegend.appendChild(document.createTextNode(' → '));
    colorLegend.appendChild(weakColor);
    colorLegend.appendChild(document.createTextNode(' → '));
    colorLegend.appendChild(veryWeakColor);
    colorLegend.appendChild(weakLabel);

    legend.appendChild(colorLegend);

    // Leyenda de distancia
    const distanceLegend = document.createElement('div');
    distanceLegend.style.display = 'flex';
    distanceLegend.style.alignItems = 'center';

    const distanceLabel = document.createElement('span');
    distanceLabel.textContent = 'Distancia relativa:';
    distanceLabel.style.marginRight = '8px';

    const distanceArrow = document.createElement('span');
    distanceArrow.textContent = '→';
    distanceArrow.style.fontSize = '1.2rem';
    distanceArrow.style.margin = '0 4px';

    const distanceText = document.createElement('span');
    distanceText.textContent = 'Más cerca';

    distanceLegend.appendChild(distanceLabel);
    distanceLegend.appendChild(distanceArrow);
    distanceLegend.appendChild(distanceText);

    legend.appendChild(distanceLegend);

    networkMapDiv.appendChild(legend);
}

// Función para mostrar detalles de una red
function showNetworkDetails(network) {
    const detailsModal = document.getElementById('network-details-modal');
    if (!detailsModal) return;

    // Crear el modal si no existe
    if (!detailsModal) {
        const modal = document.createElement('div');
        modal.id = 'network-details-modal';
        modal.className = 'network-details-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Detalles de la Red</h2>
                    <button class="close-button">×</button>
                </div>
                <div class="modal-body">
                    <div class="network-detail">
                        <div class="detail-row">
                            <span class="detail-label">Nombre de la Red (SSID):</span>
                            <span class="detail-value" id="modal-ssid"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Dirección MAC (BSSID):</span>
                            <span class="detail-value" id="modal-bssid"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fuerza de Señal (RSSI):</span>
                            <span class="detail-value" id="modal-rssi"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fabricante:</span>
                            <span class="detail-value" id="modal-manufacturer"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Tipo de Dispositivo:</span>
                            <span class="detail-value" id="modal-device-type"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha de Detección:</span>
                            <span class="detail-value" id="modal-timestamp"></span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Distancia Relativa:</span>
                            <div class="signal-graph" id="modal-signal-graph"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Agregar estilos CSS
        const style = document.createElement('style');
        style.textContent = `
            .network-details-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 9999;
                display: flex;
                justify-content: center;
                align-items: center;
                background-color: rgba(0, 0, 0, 0.7);
            }

            .modal-overlay {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.7);
            }

            .modal-content {
                background-color: var(--card-background);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 20px;
                width: 90%;
                max-width: 400px;
                max-height: 80vh;
                overflow-y: auto;
                position: relative;
                z-index: 10;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            }

            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }

            .modal-header h2 {
                color: var(--accent-color);
                margin: 0;
                font-size: 1.2rem;
            }

            .close-button {
                background: none;
                border: none;
                color: var(--text-secondary);
                font-size: 1.5rem;
                cursor: pointer;
                padding: 5px;
            }

            .modal-body {
                margin-bottom: 20px;
            }

            .network-detail {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .detail-row {
                display: flex;
                flex-wrap: wrap;
            }

            .detail-label {
                font-weight: bold;
                min-width: 140px;
                color: var(--text-primary);
            }

            .detail-value {
                color: var(--text-secondary);
                flex: 1;
            }

            .signal-graph {
                width: 100%;
                height: 20px;
                background-color: var(--border-color);
                border-radius: 10px;
                margin-top: 4px;
                overflow: hidden;
            }

            .signal-graph-fill {
                height: 100%;
                background-color: var(--accent-color);
                border-radius: 10px;
            }
        `;

        document.body.appendChild(modal);
        document.head.appendChild(style);
    }

    // Mostrar el modal
    detailsModal.style.display = 'flex';

    // Rellenar los detalles
    document.getElementById('modal-ssid').textContent = network.ssid;
    document.getElementById('modal-bssid').textContent = network.bssid;
    document.getElementById('modal-rssi').textContent = `${network.rssi} dBm`;
    document.getElementById('modal-manufacturer').textContent = network.manufacturer;
    document.getElementById('modal-device-type').textContent = network.device_type;
    document.getElementById('modal-timestamp').textContent = new Date(network.timestamp).toLocaleString();

    // Actualizar el gráfico de señal
    const signalGraph = document.getElementById('modal-signal-graph');
    if (signalGraph) {
        signalGraph.innerHTML = '';
        const fill = document.createElement('div');
        fill.className = 'signal-graph-fill';
        fill.style.width = `${Math.min(100, 100 + network.rssi)}%`;
        fill.style.backgroundColor = getSignalColor(network.rssi);
        signalGraph.appendChild(fill);
    }

    // Event listener para cerrar el modal
    const closeButton = detailsModal.querySelector('.close-button');
    if (closeButton) {
        closeButton.addEventListener('click', () => {
            detailsModal.style.display = 'none';
        });
    }

    // Cerrar modal al hacer clic fuera
    const overlay = detailsModal.querySelector('.modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', () => {
            detailsModal.style.display = 'none';
        });
    }
}

// Función para iniciar el escaneo de radar
async function startRadarScan() {
    try {
        // Mostrar estado de carga
        const startRadarScanBtn = document.getElementById('start-radar-scan');
        if (startRadarScanBtn) {
            startRadarScanBtn.disabled = true;
            startRadarScanBtn.innerHTML = '<span class="spinner"></span> Escaneando redes...';
        }

        // Escanear redes WiFi
        const networks = await scanWiFiNetworks();

        // Mostrar resultados en el dashboard
        displayScanResults(networks);

        // Enviar datos a AURA
        const response = await sendScanToAura(networks);
        console.log('Datos enviados a AURA:', response);

        // Guardar el historial localmente
        radarHistory.unshift({
            timestamp: new Date().toISOString(),
            networks: networks,
            presence_analysis: response.presence_analysis || []
        });

        // Mostrar alertas de presencia si las hay
        if (response.presence_analysis && response.presence_analysis.length > 0) {
            presenceAlerts = response.presence_analysis;
            displayPresenceAlerts(presenceAlerts);
        }

    } catch (error) {
        console.error('Error en el escaneo de radar:', error);
        const radarResultsDiv = document.getElementById('radar-results');
        if (radarResultsDiv) {
            radarResultsDiv.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
        }
    } finally {
        // Restaurar el botón
        const startRadarScanBtn = document.getElementById('start-radar-scan');
        if (startRadarScanBtn) {
            startRadarScanBtn.disabled = false;
            startRadarScanBtn.innerHTML = '🔍 Iniciar Escaneo';
        }

        // Programar el siguiente escaneo si el radar está activo
        if (radarActive) {
            scanIntervalId = setTimeout(startRadarScan, SCAN_INTERVAL);
        }
    }
}

// Función para detener el modo radar
function stopRadarMode() {
    radarActive = false;
    if (scanIntervalId) {
        clearTimeout(scanIntervalId);
        scanIntervalId = null;
    }

    // Mostrar estado en la UI
    const radarStatusDiv = document.getElementById('radar-status');
    if (radarStatusDiv) {
        radarStatusDiv.textContent = 'Estado: Inactivo';
    }

    console.log('🛑 Modo Radar detenido');
}

// Función para cambiar entre pestañas
function changeTab(tabName) {
    currentTab = tabName;

    // Ocultar todas las pestañas
    document.querySelectorAll('.radar-tab-content').forEach(content => {
        content.style.display = 'none';
    });

    // Mostrar la pestaña seleccionada
    const activeTabContent = document.getElementById(`radar-tab-${tabName}`);
    if (activeTabContent) {
        activeTabContent.style.display = 'block';
    }

    // Actualizar el estilo de los botones de pestaña
    document.querySelectorAll('.radar-tab-button').forEach(button => {
        button.classList.remove('active-tab');
    });

    const activeTabButton = document.getElementById(`tab-button-${tabName}`);
    if (activeTabButton) {
        activeTabButton.classList.add('active-tab');
    }

    // Cargar datos según la pestaña
    if (tabName === 'identification') {
        loadRadarHistory();
    } else if (tabName === 'presence') {
        loadPresenceAnalysis();
    }
}

// Función para cargar el historial de escaneos
async function loadRadarHistory() {
    try {
        const history = await getRadarHistory(20);
        radarHistory = history;

        // Mostrar los últimos escaneos
        displayScanResults(history.length > 0 ? history[0].networks : []);

        // Actualizar el gráfico de redes detectadas
        if (history.length > 0) {
            updateNetworkMapVisualization(history[0].networks);
        }
    } catch (error) {
        console.error('Error al cargar historial de radar:', error);
    }
}

// Función para cargar el análisis de presencia
async function loadPresenceAnalysis() {
    try {
        const analysis = await getPresenceAnalysis(10);
        presenceAlerts = analysis;
        displayPresenceAlerts(analysis);
    } catch (error) {
        console.error('Error al cargar análisis de presencia:', error);
    }
}

// Función para iniciar el modo radar con escaneos periódicos
function startContinuousRadarScan() {
    radarActive = true;
    lastScanTime = new Date();

    // Mostrar estado en la UI
    const radarStatusDiv = document.getElementById('radar-status');
    if (radarStatusDiv) {
        radarStatusDiv.textContent = 'Estado: Activo (Escaneando cada 10 segundos)';
    }

    // Iniciar el primer escaneo
    startRadarScan();
}

// Función principal para inicializar el módulo de radar
function initRadarModule() {
    // Verificar si los elementos del radar ya existen
    const startRadarScanBtn = document.getElementById('start-radar-scan');
    const stopRadarScanBtn = document.getElementById('stop-radar-scan');
    const radarStatusDiv = document.getElementById('radar-status');
    const identificationTabBtn = document.getElementById('tab-button-identification');
    const presenceTabBtn = document.getElementById('tab-button-presence');

    if (startRadarScanBtn && stopRadarScanBtn && radarStatusDiv &&
        identificationTabBtn && presenceTabBtn) {

        // Event listeners para los botones
        startRadarScanBtn.addEventListener('click', startContinuousRadarScan);
        stopRadarScanBtn.addEventListener('click', stopRadarMode);

        // Event listeners para cambiar de pestaña
        identificationTabBtn.addEventListener('click', () => changeTab('identification'));
        presenceTabBtn.addEventListener('click', () => changeTab('presence'));

        // Inicializar con la pestaña de identificación
        changeTab('identification');

        // Cargar datos iniciales
        loadRadarHistory();
        loadPresenceAnalysis();

        // Inicializar el contexto de audio para el centinela (si está disponible)
        if (typeof window.otaUpdater !== 'undefined') {
            window.otaUpdater.lockInterface();
        }
    }

    // Exportar funciones para que puedan ser usadas desde otros módulos
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            startRadarScan,
            stopRadarMode,
            startContinuousRadarScan,
            changeTab,
            initRadarModule
        };
    }
}

// Inicializar el módulo cuando la página esté lista
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar el módulo de radar
    initRadarModule();

    // Inicializar el módulo de actualización OTA si está disponible
    if (typeof window.otaUpdater !== 'undefined') {
        window.otaUpdater.unlockInterface();
    }
});