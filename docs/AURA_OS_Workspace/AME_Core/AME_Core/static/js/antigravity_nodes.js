/**
 * AURA Antigravity Nodes — Three.js 3D Graph
 * Sistema de partículas con física de repulsión gestual.
 * Usa MediaPipe Hands para interacción táctil sin contacto.
 * Memoria Holográfica: Nodos interactivos con datos de inspiración y mundo real.
 * Efectos visuales de producción con post-procesamiento.
 */
 /* global THREE, EffectComposer, RenderPass, UnrealBloomPass, GlitchPass, ShaderPass, GammaCorrectionShader, FXAAShader */

/**
 * Variables globales para optimización de recursos
 */
let scene = null;
let camera = null;
let renderer = null;
let composer = null;
let nodes = [];
let edges = [];
let pointerSphere = null;
let isRunning = false;
let lastIndexX = 0, lastIndexY = 0;
let inspirationData = [];
let worldDataNodes = []; // Nodos para datos del mundo real
let tooltipElement = null;
let hoverTimeout = null;
let glitchActive = false;
let glitchTimeout = null;
let alarmModeActive = false;
let lastFrameTime = 0;
let frameCount = 0;
let fps = 0;
let lastFpsUpdate = 0;
let worldStateRefreshInterval = 30000; // 30 segundos
let lastWorldStateUpdate = 0;

/**
 * Sistema de filtro de suavizado por media móvil
 */
class PositionSmoothingFilter {
    constructor(bufferSize = 5) {
        this.bufferSize = bufferSize;
        this.buffer = [];
    }

    addSample(rawX, rawY) {
        this.buffer.push({ x: rawX, y: rawY });
        if (this.buffer.length > this.bufferSize) {
            this.buffer.shift();
        }

        let sumX = 0, sumY = 0;
        for (const sample of this.buffer) {
            sumX += sample.x;
            sumY += sample.y;
        }

        const count = this.buffer.length;
        return {
            x: sumX / count,
            y: sumY / count
        };
    }

    clear() {
        this.buffer = [];
    }

    getBufferSize() {
        return this.buffer.length;
    }
}

const smoothingFilter = new PositionSmoothingFilter();

/**
 * Inicializar escena 3D con post-procesamiento
 */
function initAntigravityNodes() {
    const container = document.getElementById('antigravity-nodes');
    if (!container) {
        console.warn('Antigravity nodes: container not found');
        return;
    }

    // Configurar escena
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1a);

    // Cámara (perspectiva)
    camera = new THREE.PerspectiveCamera(75, container.offsetWidth / container.offsetHeight, 0.1, 1000);
    camera.position.z = 150;

    // Renderizador
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.offsetWidth, container.offsetHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.outputEncoding = THREE.sRGBEncoding;
    container.appendChild(renderer.domElement);

    // Configurar EffectComposer para post-procesamiento
    composer = new EffectComposer(renderer);
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    // Añadir efecto Bloom (UnrealBloomPass)
    const bloomPass = new UnrealBloomPass(
        new THREE.Vector2(container.offsetWidth, container.offsetHeight),
        1.5,  // strength
        0.4,  // radius
        0.85  // threshold
    );
    bloomPass.threshold = 0.0;
    bloomPass.strength = 0.8;
    bloomPass.radius = 0.4;
    composer.addPass(bloomPass);

    // Luz ambiental
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    // Luz direccional
    const dirLight = new THREE.DirectionalLight(0x00d4ff, 0.8);
    dirLight.position.set(1, 1, 1);
    scene.add(dirLight);

    // Crear nodos genéricos (partículas)
    createNodes(10);

    // Cargar datos de inspiración desde el backend
    loadInspirationData();

    // Cargar datos del mundo real
    loadWorldData();

    // Iniciar render loop
    isRunning = true;
    animate();

    // Configurar eventos para glitch
    setupGlitchEffects();

    // Iniciar actualización periódica de datos del mundo
    setInterval(loadWorldData, worldStateRefreshInterval);
}

/**
 * Configurar efectos de glitch para alertas
 */
function setupGlitchEffects() {
    // GlitchPass para efectos de distorsión
    const glitchPass = new GlitchPass();
    glitchPass.goWild = false;
    glitchPass.enabled = false;

    // Añadir GlitchPass al composer
    composer.addPass(glitchPass);

    // Guardar referencia al GlitchPass
    window.antigravityNodes.glitchPass = glitchPass;

    // Escuchar eventos de alerta
    document.addEventListener('systemAlert', (event) => {
        triggerGlitchEffect(event.detail.severity);
    });

    document.addEventListener('sensorAnomaly', (event) => {
        triggerGlitchEffect(event.detail.severity);
    });
}

/**
 * Activar efecto de glitch
 */
function triggerGlitchEffect(severity) {
    if (glitchActive) return;

    const glitchPass = window.antigravityNodes.glitchPass;
    if (!glitchPass) return;

    glitchActive = true;
    glitchPass.enabled = true;
    glitchPass.goWild = severity === 'critical';

    // Cambiar color de escena a rojo peligro
    const ambientLight = scene.children.find(child => child instanceof THREE.AmbientLight);
    const dirLight = scene.children.find(child => child instanceof THREE.DirectionalLight);

    if (ambientLight) {
        ambientLight.color.setHex(0xff3366);
    }

    if (dirLight) {
        dirLight.color.setHex(0xff3366);
    }

    // Restaurar después de 1.5 segundos
    glitchTimeout = setTimeout(() => {
        glitchPass.enabled = false;
        glitchPass.goWild = false;

        if (ambientLight) {
            ambientLight.color.setHex(0x404040);
        }

        if (dirLight) {
            dirLight.color.setHex(0x00d4ff);
        }

        glitchActive = false;
        clearTimeout(glitchTimeout);
    }, 1500);
}

/**
 * Cargar datos de inspiración desde el backend
 */
function loadInspirationData() {
    fetch('/api/evolution/proposals')
        .then(response => response.json())
        .then(data => {
            if (data.proposals && data.proposals.length > 0) {
                inspirationData = data.proposals.map(proposal => {
                    return {
                        title: proposal.description,
                        content: proposal.code_after || proposal.description,
                        id: proposal.inspiration_id || `node_${Math.random().toString(36).substr(2, 9)}`
                    };
                });
                console.log(`📡 Cargados ${inspirationData.length} nodos de inspiración`);
                updateNodesWithInspiration();
            } else {
                console.log('⚠️  No hay datos de inspiración disponibles');
            }
        })
        .catch(error => {
            console.error('❌ Error cargando datos de inspiración:', error);
        });
}

/**
 * Cargar datos del mundo real desde el backend
 */
function loadWorldData() {
    fetch('/api/tactical/world_state')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                const worldState = data.world_state;
                const connection = data.connection;

                // Procesar datos del mundo para crear nodos
                processWorldData(worldState, connection);

                // Actualizar timestamp de última actualización
                lastWorldStateUpdate = Date.now();
                console.log(`🌐 Datos del mundo actualizados (${connection.online ? 'en línea' : 'offline'})`);
            } else if (data.status === 'offline') {
                console.log('⚠️  Sin conexión a internet. Mostrando datos de ejemplo.');
                // Usar datos de ejemplo si no hay conexión
                const exampleData = data.world_state;
                processWorldData(exampleData, data.connection);
            } else {
                console.error('❌ Error obteniendo datos del mundo:', data.message);
            }
        })
        .catch(error => {
            console.error('❌ Error cargando datos del mundo:', error);
            // Mostrar datos de ejemplo si hay error
            showExampleWorldData();
        });
}

/**
 * Mostrar datos de ejemplo del mundo
 */
function showExampleWorldData() {
    const exampleState = {
        "timestamp": new Date().toISOString(),
        "sources": {
            "weather": {
                "status": "available",
                "data": {
                    "main": {
                        "temp": 22.5,
                        "humidity": 78,
                        "pressure": 1012
                    },
                    "weather": [{
                        "main": "Clear",
                        "description": "Cielo despejado"
                    }],
                    "wind": {
                        "speed": 3.6
                    }
                },
                "timestamp": new Date().toISOString()
            },
            "news": {
                "status": "available",
                "data": {
                    "articles": [
                        {
                            "title": "Ejemplo: Avances en IA",
                            "description": "Investigadores logran nuevos hitos en modelos de lenguaje...",
                            "publishedAt": new Date().toISOString()
                        }
                    ]
                },
                "timestamp": new Date().toISOString()
            },
            "time": {
                "status": "available",
                "data": {
                    "datetime": new Date().toISOString(),
                    "timezone": "America/Lima",
                    "day_of_week": new Date().toLocaleDateString('es-ES', { weekday: 'long' })
                },
                "timestamp": new Date().toISOString()
            }
        },
        "connection": {
            "online": false,
            "message": "Datos de ejemplo (sin conexión)"
        }
    };

    processWorldData(exampleState, {
        online: false,
        message: "Datos de ejemplo"
    });
}

/**
 * Procesar datos del mundo para crear nodos visuales
 */
function processWorldData(worldState, connection) {
    // Limpiar nodos de mundo existentes
    worldDataNodes.forEach(node => scene.remove(node));
    worldDataNodes = [];

    // Crear nodos para cada fuente de datos disponible
    const sources = worldState.sources || {};
    let nodeCount = 0;

    // Nodos para clima
    if (sources.weather && sources.weather.status === 'available') {
        const weatherData = sources.weather.data;
        const weatherNode = createWorldDataNode(
            '🌤 Clima',
            `Temp: ${weatherData.main.temp}°C\nHumedad: ${weatherData.main.humidity}%\nViento: ${weatherData.wind.speed} m/s`,
            0x00d4ff,
            nodeCount++
        );
        worldDataNodes.push(weatherNode);
    }

    // Nodos para noticias
    if (sources.news && sources.news.status === 'available') {
        const newsData = sources.news.data;
        if (newsData.articles && newsData.articles.length > 0) {
            const newsNode = createWorldDataNode(
                '📰 Noticias',
                newsData.articles[0].title + '\n' + newsData.articles[0].description.substring(0, 50) + '...',
                0xffcc00,
                nodeCount++
            );
            worldDataNodes.push(newsNode);
        }
    }

    // Nodos para tiempo
    if (sources.time && sources.time.status === 'available') {
        const timeData = sources.time.data;
        const timeNode = createWorldDataNode(
            '⏰ Hora Mundial',
            `Hora: ${new Date(timeData.datetime).toLocaleTimeString()}\nZona: ${timeData.timezone}\nDía: ${timeData.day_of_week}`,
            0xff3366,
            nodeCount++
        );
        worldDataNodes.push(timeNode);
    }

    // Nodos para criptomonedas (si están disponibles)
    if (sources.crypto && sources.crypto.status === 'available') {
        const cryptoData = sources.crypto.data;
        let cryptoContent = "💰 Criptomonedas:\n";
        for (const [coin, prices] of Object.entries(cryptoData)) {
            cryptoContent += `${coin}: $${prices.USD.toFixed(2)}\n`;
        }
        const cryptoNode = createWorldDataNode(
            '💰 Cripto',
            cryptoContent,
            0x99ff00,
            nodeCount++
        );
        worldDataNodes.push(cryptoNode);
    }

    // Nodo de estado de conexión
    const connectionNode = createWorldDataNode(
        '🌐 Conexión',
        connection.online ?
            `En línea\nÚltima actualización: ${new Date(connection.last_refresh).toLocaleString()}` :
            `Offline\n${connection.message}`,
        connection.online ? 0x00ff88 : 0xff3366,
        nodeCount++
    );
    worldDataNodes.push(connectionNode);

    // Actualizar la escena
    updateSceneWithWorldData();
}

/**
 * Crear nodo para datos del mundo real
 */
function createWorldDataNode(title, content, colorHex, index) {
    // Posición aleatoria en el espacio 3D (anillo exterior)
    const radius = 120;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI;
    const x = radius * Math.sin(phi) * Math.cos(theta);
    const y = radius * Math.sin(phi) * Math.sin(theta);
    const z = radius * Math.cos(phi);

    // Crear geometría y material
    const geometry = new THREE.SphereGeometry(4, 16, 16);
    const material = new THREE.MeshPhongMaterial({
        color: colorHex,
        emissive: 0x00d4ff,
        emissiveIntensity: 0.2,
        transparent: true,
        opacity: 0.9,
        metalness: 0.4,
        roughness: 0.1
    });

    // Crear malla
    const node = new THREE.Mesh(geometry, material);
    node.position.set(x, y, z);
    node.userData = {
        title: title,
        content: content,
        id: `world_node_${index}`,
        originalPosition: new THREE.Vector3(x, y, z),
        originalColor: material.color.clone(),
        isWorldData: true
    };

    return node;
}

/**
 * Actualizar la escena con los nodos de datos del mundo
 */
function updateSceneWithWorldData() {
    // Añadir nodos de mundo a la escena
    worldDataNodes.forEach(node => {
        if (!scene.children.includes(node)) {
            scene.add(node);
        }
    });

    // Crear conexiones entre nodos de mundo (solo si hay suficientes)
    if (worldDataNodes.length > 1) {
        createWorldDataEdges(worldDataNodes);
    }
}

/**
 * Crear conexiones entre nodos de datos del mundo
 */
function createWorldDataEdges(nodes) {
    // Limpiar conexiones existentes de datos del mundo
    edges.forEach(edge => {
        if (edge.userData && edge.userData.worldData) {
            scene.remove(edge);
        }
    });
    edges = edges.filter(edge => !(edge.userData && edge.userData.worldData));

    // Crear conexiones entre nodos de mundo
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < Math.min(nodes.length, i + 3); j++) { // Máximo 3 conexiones por nodo
            if (Math.random() > 0.6) { // 60% de probabilidad de conexión
                createEdge(nodes[i], nodes[j], true);
            }
        }
    }
}

/**
 * Actualizar nodos con datos de inspiración
 */
function updateNodesWithInspiration() {
    // Limpiar nodos existentes de inspiración
    nodes.forEach(node => {
        if (!node.userData.isWorldData) {
            scene.remove(node);
        }
    });
    nodes = nodes.filter(node => node.userData.isWorldData);

    // Crear nodos con datos de inspiración
    const nodeCount = Math.min(inspirationData.length, 30); // Máximo 30 nodos de inspiración
    for (let i = 0; i < nodeCount; i++) {
        const data = inspirationData[i];
        createDataNode(data);
    }

    // Crear conexiones aleatorias entre nodos de inspiración
    createRandomEdges(nodes.length);
}

/**
 * Crear nodo con datos de inspiración
 */
function createDataNode(data) {
    // Posición aleatoria en el espacio 3D (anillo interior)
    const radius = 80;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI;
    const x = radius * Math.sin(phi) * Math.cos(theta);
    const y = radius * Math.sin(phi) * Math.sin(theta);
    const z = radius * Math.cos(phi);

    // Crear geometría y material
    const geometry = new THREE.SphereGeometry(3, 16, 16);
    const material = new THREE.MeshPhongMaterial({
        color: getNodeColor(nodes.length + worldDataNodes.length),
        emissive: 0x00d4ff,
        emissiveIntensity: 0.1,
        transparent: true,
        opacity: 0.8,
        metalness: 0.3,
        roughness: 0.2
    });

    // Crear malla
    const node = new THREE.Mesh(geometry, material);
    node.position.set(x, y, z);
    node.userData = {
        title: data.title,
        content: data.content,
        id: data.id,
        originalPosition: new THREE.Vector3(x, y, z),
        originalColor: material.color.clone(),
        isWorldData: false
    };

    // Añadir al array de nodos y a la escena
    nodes.push(node);
    scene.add(node);
}

/**
 * Crear nodos genéricos (sin datos)
 */
function createNodes(count) {
    for (let i = 0; i < count; i++) {
        const radius = 100;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        const x = radius * Math.sin(phi) * Math.cos(theta);
        const y = radius * Math.sin(phi) * Math.sin(theta);
        const z = radius * Math.cos(phi);

        const geometry = new THREE.SphereGeometry(3, 16, 16);
        const material = new THREE.MeshPhongMaterial({
            color: getNodeColor(i),
            emissive: 0x00d4ff,
            emissiveIntensity: 0.1,
            transparent: true,
            opacity: 0.8,
            metalness: 0.3,
            roughness: 0.2
        });

        const node = new THREE.Mesh(geometry, material);
        node.position.set(x, y, z);
        node.userData = {
            title: `Nodo ${i + 1}`,
            content: 'Sin datos de inspiración',
            id: `node_${i}`,
            originalPosition: new THREE.Vector3(x, y, z),
            originalColor: material.color.clone(),
            isWorldData: false
        };

        nodes.push(node);
        scene.add(node);
    }
}

/**
 * Obtener color para nodo basado en su índice
 */
function getNodeColor(index) {
    const colors = [
        0x00d4ff, 0xff3366, 0x00ff88, 0xffcc00,
        0xff6600, 0xcc00ff, 0x00ccff, 0xff9900,
        0x99ff00, 0xff00cc, 0xccff00, 0x00ffff,
        0xff66cc, 0xcc66ff, 0x66ccff, 0xccff66
    ];
    return colors[index % colors.length];
}

/**
 * Crear conexiones aleatorias entre nodos
 */
function createRandomEdges(nodeCount) {
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < Math.min(nodes.length, i + 5); j++) { // Máximo 5 conexiones por nodo
            if (Math.random() > 0.7) { // 70% de probabilidad de conexión
                createEdge(nodes[i], nodes[j]);
            }
        }
    }
}

/**
 * Crear conexión entre dos nodos
 */
function createEdge(node1, node2, isWorldData = false) {
    const points = [];
    points.push(node1.position);
    points.push(node2.position);

    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
        color: 0x333333,
        linewidth: 0.3,
        transparent: true,
        opacity: 0.2
    });

    const edge = new THREE.Line(geometry, material);
    edge.userData = {
        worldData: isWorldData
    };
    edges.push(edge);
    scene.add(edge);
}

/**
 * Manejar interacción con nodos (hover)
 */
function handleNodeHover() {
    if (!nodes.length || !worldDataNodes.length || !tooltipElement) return;

    // Obtener posición del puntero en coordenadas 3D
    const pointerPos3D = mapDOMToWorld3D(lastIndexX, lastIndexY, camera, renderer.domElement);

    // Buscar nodos cercanos (tanto de inspiración como de mundo)
    const hoverDistance = 0.08; // Radio de interacción
    const hoveredNodes = [];

    // Buscar en nodos de inspiración
    nodes.forEach(node => {
        const distance = pointerPos3D.distanceTo(node.position);
        if (distance < hoverDistance) {
            hoveredNodes.push(node);
        }
    });

    // Buscar en nodos de mundo
    worldDataNodes.forEach(node => {
        const distance = pointerPos3D.distanceTo(node.position);
        if (distance < hoverDistance) {
            hoveredNodes.push(node);
        }
    });

    // Mostrar tooltip para el nodo más cercano
    if (hoveredNodes.length > 0) {
        const closestNode = hoveredNodes.reduce((prev, current) =>
            pointerPos3D.distanceTo(prev.position) < pointerPos3D.distanceTo(current.position) ? prev : current
        );

        // Mostrar tooltip
        tooltipElement.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 5px;">${closestNode.userData.title}</div>
            <div style="font-size: 11px; text-align: left; word-wrap: break-word;">${closestNode.userData.content}</div>
        `;

        // Posicionar tooltip en la pantalla
        const screenPos = closestNode.position.clone().project(camera);
        const x = (screenPos.x * 0.5 + 0.5) * renderer.domElement.offsetWidth;
        const y = -(screenPos.y * 0.5 + 0.5) * renderer.domElement.offsetHeight;

        tooltipElement.style.left = `${x}px`;
        tooltipElement.style.top = `${y}px`;
        tooltipElement.style.display = 'block';

        // Mostrar con fade in
        tooltipElement.style.opacity = '1';

        // Limpiar timeout anterior
        if (hoverTimeout) {
            clearTimeout(hoverTimeout);
        }

        // Ocultar tooltip después de 5 segundos de inactividad
        hoverTimeout = setTimeout(() => {
            tooltipElement.style.opacity = '0';
            setTimeout(() => {
                tooltipElement.style.display = 'none';
            }, 300);
        }, 5000);
    } else {
        // Ocultar tooltip si no hay nodos cercanos
        if (tooltipElement.style.display === 'block') {
            tooltipElement.style.opacity = '0';
            setTimeout(() => {
                tooltipElement.style.display = 'none';
            }, 300);
        }
    }
}

/**
 * Mapear coordenadas DOM a posición 3D en el espacio de Three.js
 */
function mapDOMToWorld3D(domX, domY, camera, canvas) {
    // Normalizar coordenadas DOM a rango [-1, 1] (formato NDC)
    const rect = canvas.getBoundingClientRect();
    const x = ((domX - rect.left) / rect.width) * 2 - 1;
    const y = -((domY - rect.top) / rect.height) * 2 + 1;

    // Vector ray desde cámara a través del punto NDC
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(x, y), camera);

    // Usar posición a distancia fija en frente de la cámara (plano de interacción)
    const interactionDistance = 5;
    const worldPos = new THREE.Vector3();
    raycaster.ray.getPointAt(interactionDistance, worldPos);

    return worldPos;
}

/**
 * Animación principal con post-procesamiento
 */
function animate() {
    if (!isRunning) return;

    requestAnimationFrame(animate);

    // Rotar cámara suavemente
    camera.position.x = Math.sin(Date.now() * 0.0005) * 50;
    camera.position.y = Math.cos(Date.now() * 0.0005) * 50;
    camera.lookAt(0, 0, 0);

    // Actualizar nodos con física de repulsión
    updateNodes();

    // Renderizar escena con post-procesamiento
    composer.render();

    // Actualizar FPS cada segundo
    const now = Date.now();
    frameCount++;
    if (now - lastFpsUpdate > 1000) {
        fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
        frameCount = 0;
        lastFpsUpdate = now;
    }
}

/**
 * Actualizar nodos con física de repulsión
 */
function updateNodes() {
    // Actualizar nodos de inspiración
    nodes.forEach(node => {
        if (!node.userData.isWorldData) {
            // Aplicar repulsión suave
            const direction = new THREE.Vector3()
                .subVectors(node.position, new THREE.Vector3(0, 0, 0))
                .normalize()
                .multiplyScalar(0.01);

            node.position.add(direction);

            // Limitar posición para evitar que se escape
            const distance = node.position.length();
            if (distance > 80) {
                node.position.normalize().multiplyScalar(80);
            }
        }
    });

    // Actualizar nodos de mundo (menos repulsión para que se mantengan en su posición)
    worldDataNodes.forEach(node => {
        if (node.userData.isWorldData) {
            // Aplicar repulsión muy suave para mantenerlos en su posición
            const direction = new THREE.Vector3()
                .subVectors(node.position, new THREE.Vector3(0, 0, 0))
                .normalize()
                .multiplyScalar(0.002);

            node.position.add(direction);

            // Limitar posición para evitar que se escape
            const distance = node.position.length();
            if (distance > 120) {
                node.position.normalize().multiplyScalar(120);
            }
        }
    });
}

/**
 * Configurar modo alarma (iluminación roja)
 */
function setAlarmMode(active) {
    alarmModeActive = active;

    const ambientLight = scene.children.find(child => child instanceof THREE.AmbientLight);
    const dirLight = scene.children.find(child => child instanceof THREE.DirectionalLight);

    if (active) {
        if (ambientLight) {
            ambientLight.color.setHex(0xff3366);
            ambientLight.intensity = 0.8;
        }

        if (dirLight) {
            dirLight.color.setHex(0xff3366);
            dirLight.intensity = 1.2;
        }

        // Aumentar velocidad de rotación de la cámara
        camera.rotationSpeed = 0.005;
    } else {
        if (ambientLight) {
            ambientLight.color.setHex(0x404040);
            ambientLight.intensity = 0.5;
        }

        if (dirLight) {
            dirLight.color.setHex(0x00d4ff);
            dirLight.intensity = 0.8;
        }

        // Restaurar velocidad de rotación de la cámara
        camera.rotationSpeed = 0.0005;
    }
}

/**
 * Modo bajo FPS para ahorro de recursos
 */
function setLowFpsMode(active) {
    if (active) {
        // Reducir calidad de renderizado
        renderer.setAnimationLoop(null);
        renderer.setSize(renderer.domElement.offsetWidth / 2, renderer.domElement.offsetHeight / 2);
        renderer.setPixelRatio(0.5);
    } else {
        // Restaurar calidad
        renderer.setAnimationLoop(animate);
        renderer.setSize(renderer.domElement.offsetWidth, renderer.domElement.offsetHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
    }
}

/**
 * Iniciar render loop cuando el DOM esté listo
 */
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initAntigravityNodes();
} else {
    document.addEventListener('DOMContentLoaded', initAntigravityNodes);
}

/**
 * Manejar redimensionamiento de la ventana
 */
window.addEventListener('resize', () => {
    if (renderer) {
        camera.aspect = renderer.domElement.offsetWidth / renderer.domElement.offsetHeight;
        camera.updateProjectionMatrix();

        // Actualizar EffectComposer
        if (composer) {
            composer.setSize(renderer.domElement.offsetWidth, renderer.domElement.offsetHeight);
        }

        renderer.setSize(renderer.domElement.offsetWidth, renderer.domElement.offsetHeight);
    }
});

/**
 * Exportar funciones para interacción con hologram_gestures.js
 */
window.antigravityNodes = {
    updatePointerPosition: (x, y) => {
        lastIndexX = x;
        lastIndexY = y;
        handleNodeHover();
    },
    getInspirationData: () => inspirationData,
    getWorldData: () => worldDataNodes,
    getTooltipElement: () => tooltipElement,
    setAlarmMode: (active) => setAlarmMode(active),
    setLowFpsMode: (active) => setLowFpsMode(active),
    updateNodes: updateNodes,
    triggerGlitchEffect: (severity) => triggerGlitchEffect(severity),
    getScene: () => scene,
    getCamera: () => camera,
    getRenderer: () => renderer,
    getComposer: () => composer,
    refreshWorldData: loadWorldData
};
