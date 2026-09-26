/**
 * knowledge_nodes.js - Módulo para crear nodos tácticos de conocimiento en 3D
 * Integra la base de conocimiento de Obsidian con el motor de física Antigravity
 * Implementa análisis de grafo, conexiones físicas y filtrado dinámico
 */

// Configuración global para los nodos de conocimiento
const KNOWLEDGE_NODES_CONFIG = {
    baseSize: 4,          // Tamaño base de los nodos
    minSize: 3,          // Tamaño mínimo
    maxSize: 8,          // Tamaño máximo
    categoryColors: {
        'shadow-core': 0xff3366,    // Rosa para Shadow-Core
        'physics': 0x00d4ff,        // Azul para Physics
        'obsidian': 0x00ff88,       // Verde para Obsidian
        'default': 0x8888ff         // Morado por defecto
    },
    nodeSpacing: 15,      // Espaciado entre nodos
    glowIntensity: 0.5,   // Intensidad del efecto de brillo
    panelDuration: 3000, // Duración del panel de conocimiento (ms)
    panelZIndex: 2000,    // Z-index para los paneles
    connectionLines: true, // Mostrar líneas de conexión entre nodos
    connectionStrength: 0.5, // Fuerza base de las conexiones
    maxConnections: 10,   // Máximo de conexiones por nodo
    searchHighlightOpacity: 0.9, // Opacidad para nodos destacados
    searchFadeOpacity: 0.2,   // Opacidad para nodos no relacionados
    threatColor: 0xff3366,    // Color para nodos en amenaza
    normalColor: 0x00d4ff,    // Color normal para nodos
    connectionTypes: {
        'depends_on': { color: 0x00d4ff, width: 2, dashed: false, strength: 0.9, alpha: 0.6 },
        'related_to': { color: 0x00ff88, width: 1.5, dashed: false, strength: 0.7, alpha: 0.5 },
        'uses': { color: 0xffcc00, width: 1, dashed: true, strength: 0.5, alpha: 0.4 },
        'implemented_by': { color: 0x8888ff, width: 1.5, dashed: true, strength: 0.8, alpha: 0.5 },
        'extends': { color: 0xff66cc, width: 1.5, dashed: false, strength: 0.8, alpha: 0.6 },
        'visualizes': { color: 0x00ccff, width: 1.5, dashed: false, strength: 0.7, alpha: 0.5 },
        'enhances': { color: 0xccff00, width: 1, dashed: true, strength: 0.6, alpha: 0.4 },
        'stores': { color: 0xff6600, width: 1, dashed: true, strength: 0.5, alpha: 0.4 }
    },
    physicsConstraints: true, // Activar restricciones físicas
    constraintDamping: 0.3,     // Amortiguación para las restricciones
    constraintStiffness: 100,    // Rigidez de las restricciones
    pulseEffect: true,         // Activar efecto de pulso para amenazas
    pulseDuration: 1000,       // Duración del efecto de pulso (ms)
    pulseIntensity: 0.2,       // Intensidad del efecto de pulso
    connectionLineMaterial: null, // Material para líneas de conexión
    connectionLineGeometry: null, // Geometría para líneas de conexión
    connectionLineMesh: null,   // Malla para líneas de conexión
    distanceConstraints: [],  // Array para restricciones de distancia
    connectionUpdateInterval: 1000/60, // ~60fps para actualización de conexiones
    cyberWireStyle: true,      // Estilo de línea tipo "cyber-wire"
    connectionLineWidth: 0.5,  // Grosor de las líneas de conexión
    connectionLineAlpha: 0.7,   // Transparencia base de las líneas
    connectionLineGlow: true,  // Efecto de brillo en las líneas
    connectionLineGlowIntensity: 0.3 // Intensidad del brillo en las líneas
};

// Variables globales para los nodos de conocimiento
let knowledgeNodes = [];
let knowledgeCategories = {};
let activeKnowledgePanel = null;
let connectionLines = [];
let connectionLineMaterial;
let physicsConstraints = [];
let knowledgeGraph = {};
let searchHighlightedNodes = [];
let threatActiveNodes = [];
let animationFrameId = null;
let lastUpdateTime = 0;
let connectionUpdateInterval = 1000 / 60; // ~60fps
let connectionLineMeshes = [];
let connectionLineGroups = {};

// Función para cargar la base de conocimiento
async function loadKnowledgeBase() {
    try {
        // Leer el archivo knowledge_base.json
        const response = await fetch('/knowledge_base.json');
        const data = await response.json();

        // Procesar las categorías
        for (const [categoryId, category] of Object.entries(data.categories)) {
            knowledgeCategories[categoryId] = category;
        }

        // Procesar el grafo de conocimiento
        processKnowledgeGraph(data);

        // Crear nodos para cada nota
        for (const [notePath, note] of Object.entries(data.notes)) {
            if (note.links) {
                createKnowledgeNode(note, data);
            }
        }

        // Crear material para las líneas de conexión
        createConnectionLineMaterial();

        console.log("✅ Base de conocimiento cargada con éxito");
        console.log(`   - ${Object.keys(knowledgeCategories).length} categorías`);
        console.log(`   - ${knowledgeNodes.length} nodos de conocimiento`);
        console.log(`   - ${calculateTotalConnections()} relaciones detectadas`);

        // Iniciar animación de actualización
        startConnectionAnimation();

        return true;
    } catch (error) {
        console.error("❌ Error cargando la base de conocimiento:", error);
        return false;
    }
}

// Función para procesar el grafo de conocimiento
function processKnowledgeGraph(data) {
    knowledgeGraph = {};

    // Procesar relaciones directas desde el campo 'links'
    for (const [notePath, note] of Object.entries(data.notes)) {
        if (note.links) {
            knowledgeGraph[notePath] = {
                node: note,
                connections: []
            };

            // Procesar cada conexión
            note.links.forEach(link => {
                const connection = {
                    target: link.target,
                    type: link.type,
                    strength: link.strength || 0.5,
                    description: link.description || ''
                };

                knowledgeGraph[notePath].connections.push(connection);
            });
        }
    }

    // Procesar relaciones del índice de búsqueda (si existen)
    if (data.search_index && data.search_index.node_relationships) {
        for (const [notePath, relationships] of Object.entries(data.search_index.node_relationships)) {
            if (!knowledgeGraph[notePath]) {
                knowledgeGraph[notePath] = {
                    node: data.notes[notePath],
                    connections: []
                };
            }

            // Añadir relaciones del índice
            for (const [relType, targets] of Object.entries(relationships)) {
                targets.forEach(target => {
                    const existingConnection = knowledgeGraph[notePath].connections.find(
                        c => c.target === target && c.type === relType
                    );

                    if (!existingConnection) {
                        knowledgeGraph[notePath].connections.push({
                            target: target,
                            type: relType,
                            strength: KNOWLEDGE_NODES_CONFIG.connectionTypes[relType]?.strength || 0.5,
                            description: `Relación ${relType} desde índice de búsqueda`
                        });
                    }
                });
            }
        }
    }

    // Procesar relaciones desde el campo 'related_to' (si existe)
    for (const [notePath, note] of Object.entries(data.notes)) {
        if (note.related_to && !knowledgeGraph[notePath]) {
            knowledgeGraph[notePath] = {
                node: note,
                connections: []
            };

            note.related_to.forEach(relation => {
                knowledgeGraph[notePath].connections.push({
                    target: relation.target,
                    type: relation.type || 'related_to',
                    strength: relation.strength || 0.5,
                    description: relation.description || ''
                });
            });
        }
    }

    console.log(`🌐 Grafo de conocimiento procesado con ${Object.keys(knowledgeGraph).length} nodos y ${calculateTotalConnections()} conexiones`);
}

// Función para calcular el número total de conexiones
function calculateTotalConnections() {
    let total = 0;
    for (const [notePath, nodeData] of Object.entries(knowledgeGraph)) {
        total += nodeData.connections.length;
    }
    return total;
}

// Función para crear material para líneas de conexión
function createConnectionLineMaterial() {
    // Crear un grupo para las líneas de conexión
    connectionLineGroups = {
        all: new THREE.Group(),
        byType: {}
    };

    // Añadir grupo principal a la escena
    window.threeScene.add(connectionLineGroups.all);

    // Crear material base para las líneas
    const baseMaterial = new THREE.LineBasicMaterial({
        transparent: true,
        opacity: KNOWLEDGE_NODES_CONFIG.connectionLineAlpha,
        blending: THREE.AdditiveBlending,
        depthTest: false,
        linewidth: KNOWLEDGE_NODES_CONFIG.connectionLineWidth
    });

    // Crear material con efecto de brillo para las líneas
    const glowMaterial = new THREE.LineBasicMaterial({
        transparent: true,
        opacity: KNOWLEDGE_NODES_CONFIG.connectionLineGlowIntensity,
        blending: THREE.AdditiveBlending,
        depthTest: false,
        linewidth: KNOWLEDGE_NODES_CONFIG.connectionLineWidth * 1.5,
        color: 0xffffff
    });

    // Crear geometría para líneas
    KNOWLEDGE_NODES_CONFIG.connectionLineGeometry = new THREE.BufferGeometry();

    // Crear malla para líneas (usaremos LineSegments)
    KNOWLEDGE_NODES_CONFIG.connectionLineMesh = new THREE.LineSegments(
        KNOWLEDGE_NODES_CONFIG.connectionLineGeometry,
        baseMaterial
    );

    // Añadir la malla principal al grupo
    connectionLineGroups.all.add(KNOWLEDGE_NODES_CONFIG.connectionLineMesh);

    // Guardar materiales para referencia
    KNOWLEDGE_NODES_CONFIG.connectionLineMaterial = {
        base: baseMaterial,
        glow: glowMaterial
    };

    console.log("🔗 Materiales para líneas de conexión creados");
}

// Función para crear un nodo de conocimiento
function createKnowledgeNode(note, data) {
    // Determinar la categoría
    let categoryId = 'default';
    for (const [catId, category] of Object.entries(data.categories)) {
        if (category.nodes.includes(note.path)) {
            categoryId = catId;
            break;
        }
    }

    // Determinar el tamaño del nodo basado en la relevancia
    const chunkCount = note.chunks ? note.chunks.length : 1;
    const linkCount = note.links ? note.links.length : 0;
    const size = KNOWLEDGE_NODES_CONFIG.baseSize +
                 (chunkCount * 0.5) +
                 (linkCount * 0.4) +
                 (categoryId === 'shadow-core' ? 0.8 : 0);

    // Limitar el tamaño
    const finalSize = Math.min(
        Math.max(size, KNOWLEDGE_NODES_CONFIG.minSize),
        KNOWLEDGE_NODES_CONFIG.maxSize
    );

    // Determinar el color basado en la categoría
    const color = KNOWLEDGE_NODES_CONFIG.categoryColors[categoryId] ||
                  KNOWLEDGE_NODES_CONFIG.categoryColors['default'];

    // Calcular posición basada en el hash para distribución más uniforme
    const hash = note.hash || note.path;
    const hashCode = stringToHashCode(hash);
    const position = {
        x: (hashCode % 30) - 15,  // Distribuir en rango -15 a 15
        y: (Math.floor(hashCode / 30) % 20) - 10,  // Distribuir en rango -10 a 10
        z: (Math.floor(hashCode / 600) % 10) * 2  // Distribuir en capas
    };

    // Ajustar posición según categoría
    if (categoryId === 'shadow-core') position.y += 5;
    if (categoryId === 'physics') position.y -= 5;

    // Crear el nodo físico
    const node = window.PhysicsUI.createObject({
        mass: 0.8 + (finalSize * 0.1), // Masa proporcional al tamaño
        width: finalSize,
        height: finalSize,
        depth: finalSize * 0.6,
        color: color,
        position: position,
        userData: {
            type: 'knowledge',
            category: categoryId,
            title: note.title,
            path: note.path,
            content: note.content,
            chunks: note.chunks,
            tags: note.tags,
            created: note.created,
            modified: note.modified,
            originalSize: finalSize,
            originalColor: color,
            nodeData: knowledgeGraph[note.path] || { node: note, connections: [] }
        },
        isDraggable: true
    });

    // Añadir efecto de brillo
    addGlowEffect(node.mesh, color);

    // Hacer el nodo interactivo
    makeNodeInteractive(node);

    // Guardar referencia al nodo
    knowledgeNodes.push(node);

    // Crear conexiones con otros nodos
    createNodeConnections(node, data);

    return node;
}

// Función para convertir un string a código hash
function stringToHashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash);
}

// Función para crear conexiones entre nodos
function createNodeConnections(node, data) {
    const nodePath = node.userData.path;
    const nodeData = knowledgeGraph[nodePath];

    if (!nodeData || !nodeData.connections || nodeData.connections.length === 0) {
        return;
    }

    // Limitar el número de conexiones para evitar sobrecarga
    const connectionsToCreate = Math.min(
        nodeData.connections.length,
        KNOWLEDGE_NODES_CONFIG.maxConnections
    );

    // Crear conexiones con los nodos más fuertes
    nodeData.connections.sort((a, b) => b.strength - a.strength);

    for (let i = 0; i < connectionsToCreate; i++) {
        const connection = nodeData.connections[i];
        const targetPath = connection.target;

        // Verificar si el nodo objetivo existe
        const targetNode = knowledgeNodes.find(n => n.userData.path === targetPath);
        if (!targetNode) continue;

        // Crear la conexión visual
        createConnectionLine(node, targetNode, connection);

        // Crear la restricción física si está activada
        if (KNOWLEDGE_NODES_CONFIG.physicsConstraints) {
            createPhysicsConstraint(node, targetNode, connection);
        }
    }
}

// Función para añadir efecto de brillo a un nodo
function addGlowEffect(mesh, color) {
    // Crear material con efecto de brillo
    const glowMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.3,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });

    // Crear malla de brillo (un poco más grande)
    const glowGeometry = new THREE.SphereGeometry(
        mesh.geometry.parameters.width * 1.2,
        16,
        16
    );

    const glowMesh = new THREE.Mesh(glowGeometry, glowMaterial);
    glowMesh.position.copy(mesh.position);
    glowMesh.userData = { originalPosition: mesh.position.clone() };

    // Añadir al escenario
    window.threeScene.add(glowMesh);

    // Guardar referencia para actualizar la posición
    mesh.userData.glowMesh = glowMesh;

    // Función para actualizar la posición del brillo
    mesh.userData.updateGlow = function() {
        if (this.userData.glowMesh) {
            this.userData.glowMesh.position.copy(this.position);
        }
    };
}

// Función para hacer un nodo interactivo
function makeNodeInteractive(node) {
    // Añadir evento de clic
    node.mesh.userData.onClick = function() {
        showKnowledgePanel(node.userData);
    };

    // Añadir evento de doble clic para expandir/contraer
    node.mesh.userData.onDoubleClick = function() {
        if (node.userData.expanded) {
            collapseKnowledgeNode(node);
        } else {
            expandKnowledgeNode(node);
        }
    };

    // Añadir evento de arrastre
    node.mesh.userData.onDragStart = function() {
        // Detener la animación de expansión si está activa
        if (this.userData.expanding) {
            cancelAnimationFrame(this.userData.expandAnimationId);
            this.userData.expanding = false;
        }
    };
}

// Función para crear una línea de conexión entre dos nodos
function createConnectionLine(node1, node2, connectionData) {
    if (!KNOWLEDGE_NODES_CONFIG.connectionLines) return;

    // Obtener configuración de la conexión
    const connectionType = connectionData.type || 'related_to';
    const config = KNOWLEDGE_NODES_CONFIG.connectionTypes[connectionType] || {
        color: 0x8888ff,
        width: 1,
        dashed: false,
        strength: 0.5,
        alpha: 0.5
    };

    // Crear material para esta conexión específica
    const lineMaterial = new THREE.LineBasicMaterial({
        color: config.color,
        transparent: true,
        opacity: config.alpha,
        linewidth: KNOWLEDGE_NODES_CONFIG.connectionLineWidth,
        blending: THREE.AdditiveBlending,
        depthTest: false
    });

    // Crear material de brillo para esta conexión
    const glowMaterial = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: config.alpha * 0.5,
        linewidth: KNOWLEDGE_NODES_CONFIG.connectionLineWidth * 1.2,
        blending: THREE.AdditiveBlending,
        depthTest: false
    });

    // Crear geometría para la línea (usaremos LineSegments)
    const geometry = new THREE.BufferGeometry();

    // Crear línea con geometría dinámica
    const line = new THREE.LineSegments(geometry, lineMaterial);
    line.userData = {
        node1: node1,
        node2: node2,
        type: connectionType,
        strength: config.strength,
        visible: true,
        dashed: config.dashed,
        material: lineMaterial,
        glowMaterial: glowMaterial
    };

    // Añadir la línea al grupo principal
    connectionLineGroups.all.add(line);

    // Añadir la línea al grupo por tipo si no existe
    if (!connectionLineGroups.byType[connectionType]) {
        connectionLineGroups.byType[connectionType] = new THREE.Group();
        connectionLineGroups.all.add(connectionLineGroups.byType[connectionType]);
    }
    connectionLineGroups.byType[connectionType].add(line);

    // Guardar referencia a la línea
    connectionLineMeshes.push(line);

    // Función para actualizar la línea
    line.update = function() {
        if (!this.userData.visible) return;

        const points = [];
        const node1Pos = this.userData.node1.mesh.position;
        const node2Pos = this.userData.node2.mesh.position;

        // Punto de inicio (centro del nodo 1)
        points.push(new THREE.Vector3(
            node1Pos.x,
            node1Pos.y,
            node1Pos.z
        ));

        // Punto de fin (centro del nodo 2)
        points.push(new THREE.Vector3(
            node2Pos.x,
            node2Pos.y,
            node2Pos.z
        ));

        // Actualizar geometría
        geometry.setFromPoints(points);
    };

    // Inicializar la línea
    line.update();

    console.log(`🔗 Línea de conexión creada: ${node1.userData.title} → ${node2.userData.title} (${connectionType})`);
}

// Función para crear una restricción física entre dos nodos usando DistanceConstraint
function createPhysicsConstraint(node1, node2, connectionData) {
    if (!KNOWLEDGE_NODES_CONFIG.physicsConstraints || !window.CANNON) return;

    // Obtener configuración de la conexión
    const connectionType = connectionData.type || 'related_to';
    const config = KNOWLEDGE_NODES_CONFIG.connectionTypes[connectionType] || {
        strength: 0.5
    };

    // Calcular distancia entre los nodos
    const node1Pos = node1.mesh.position;
    const node2Pos = node2.mesh.position;
    const distance = node1Pos.distanceTo(node2Pos);

    // Crear restricción de distancia (DistanceConstraint)
    const constraint = new CANNON.DistanceConstraint(
        node1.body,
        node2.body,
        distance * (1.0 - (config.strength * 0.2)) // Ajustar distancia según fuerza
    );

    // Configurar propiedades de la restricción
    constraint.setStiffness(config.strength * 100);
    constraint.setDamping(KNOWLEDGE_NODES_CONFIG.constraintDamping);

    // Añadir restricción al mundo físico
    window.physicsWorld.addConstraint(constraint);

    // Guardar referencia a la restricción
    if (!KNOWLEDGE_NODES_CONFIG.distanceConstraints) {
        KNOWLEDGE_NODES_CONFIG.distanceConstraints = [];
    }
    KNOWLEDGE_NODES_CONFIG.distanceConstraints.push({
        constraint: constraint,
        node1: node1,
        node2: node2,
        type: connectionType,
        strength: config.strength
    });

    console.log(`🔗 Restricción física creada: ${node1.userData.title} ↔ ${node2.userData.title} (${connectionType})`);
}

// Función para mostrar el panel de conocimiento
function showKnowledgePanel(noteData) {
    // Cerrar cualquier panel activo
    if (activeKnowledgePanel) {
        closeKnowledgePanel();
    }

    // Crear el contenedor del panel
    const panelContainer = document.createElement('div');
    panelContainer.className = 'knowledge-panel-container';
    panelContainer.style.position = 'fixed';
    panelContainer.style.zIndex = KNOWLEDGE_NODES_CONFIG.panelZIndex;
    panelContainer.style.width = '400px';
    panelContainer.style.height = '500px';
    panelContainer.style.left = '50%';
    panelContainer.style.top = '50%';
    panelContainer.style.transform = 'translate(-50%, -50%)';
    panelContainer.style.background = 'rgba(10, 15, 26, 0.9)';
    panelContainer.style.border = '1px solid rgba(0, 212, 255, 0.3)';
    panelContainer.style.borderRadius = '10px';
    panelContainer.style.boxShadow = '0 0 30px rgba(0, 212, 255, 0.3)';
    panelContainer.style.backdropFilter = 'blur(10px)';
    panelContainer.style.overflow = 'hidden';
    panelContainer.style.display = 'none';
    panelContainer.style.transition = 'all 0.3s ease';

    // Crear el contenido del panel
    const panelContent = document.createElement('div');
    panelContent.className = 'knowledge-panel-content';
    panelContent.style.padding = '15px';
    panelContent.style.color = '#00d4ff';
    panelContent.style.fontFamily = "'Courier New', monospace";
    panelContent.style.fontSize = '12px';
    panelContent.style.lineHeight = '1.4';
    panelContent.style.height = '100%';
    panelContent.style.overflowY = 'auto';

    // Crear el encabezado del panel
    const panelHeader = document.createElement('div');
    panelHeader.className = 'knowledge-panel-header';
    panelHeader.style.marginBottom = '15px';
    panelHeader.style.paddingBottom = '10px';
    panelHeader.style.borderBottom = '1px solid rgba(0, 212, 255, 0.1)';

    // Título del panel
    const panelTitle = document.createElement('h2');
    panelTitle.textContent = noteData.title;
    panelTitle.style.color = '#ff3366';
    panelTitle.style.margin = '0 0 5px 0';
    panelTitle.style.fontSize = '16px';

    // Ruta de la nota
    const panelPath = document.createElement('div');
    panelPath.textContent = noteData.path;
    panelPath.style.color = '#ccc';
    panelPath.style.fontSize = '11px';
    panelPath.style.marginBottom = '10px';

    // Tags
    const tagsContainer = document.createElement('div');
    tagsContainer.style.display = 'flex';
    tagsContainer.style.flexWrap = 'wrap';
    tagsContainer.style.gap = '5px';
    tagsContainer.style.marginBottom = '15px';

    noteData.tags.forEach(tag => {
        const tagElement = document.createElement('span');
        tagElement.textContent = `#${tag}`;
        tagElement.style.background = 'rgba(0, 212, 255, 0.2)';
        tagElement.style.padding = '2px 6px';
        tagElement.style.borderRadius = '12px';
        tagElement.style.fontSize = '10px';
        tagElement.style.color = '#00d4ff';
        tagsContainer.appendChild(tagElement);
    });

    // Fechas
    const datesContainer = document.createElement('div');
    datesContainer.style.display = 'flex';
    datesContainer.style.justifyContent = 'space-between';
    datesContainer.style.fontSize = '10px';
    datesContainer.style.color = '#666';

    const createdDate = document.createElement('div');
    createdDate.textContent = `Creado: ${noteData.created}`;
    createdDate.style.marginRight = '15px';

    const modifiedDate = document.createElement('div');
    modifiedDate.textContent = `Modificado: ${noteData.modified}`;

    datesContainer.appendChild(createdDate);
    datesContainer.appendChild(modifiedDate);

    // Añadir elementos al encabezado
    panelHeader.appendChild(panelTitle);
    panelHeader.appendChild(panelPath);
    panelHeader.appendChild(tagsContainer);
    panelHeader.appendChild(datesContainer);

    // Contenido principal
    const contentTitle = document.createElement('h3');
    contentTitle.textContent = 'Contenido';
    contentTitle.style.color = '#00d4ff';
    contentTitle.style.margin = '15px 0 10px 0';
    contentTitle.style.fontSize = '14px';

    // Procesar el contenido para mostrarlo con formato
    const contentDiv = document.createElement('div');
    contentDiv.style.whiteSpace = 'pre-wrap';
    contentDiv.style.lineHeight = '1.5';

    // Dividir el contenido en párrafos
    const paragraphs = noteData.content.split('\n\n').filter(p => p.trim().length > 0);

    paragraphs.forEach(paragraph => {
        const pElement = document.createElement('p');
        pElement.textContent = paragraph;
        pElement.style.margin = '5px 0';
        pElement.style.color = '#ccc';

        // Resaltar encabezados
        if (paragraph.startsWith('## ')) {
            pElement.style.fontWeight = 'bold';
            pElement.style.color = '#00d4ff';
            pElement.style.marginTop = '15px';
        } else if (paragraph.startsWith('### ')) {
            pElement.style.fontWeight = 'bold';
            pElement.style.color = '#00ff88';
            pElement.style.marginTop = '10px';
        }

        contentDiv.appendChild(pElement);
    });

    // Sección de conexiones
    const connectionsTitle = document.createElement('h3');
    connectionsTitle.textContent = 'Relaciones';
    connectionsTitle.style.color = '#00ff88';
    connectionsTitle.style.margin = '20px 0 10px 0';
    connectionsTitle.style.fontSize = '14px';

    const connectionsDiv = document.createElement('div');
    connectionsDiv.style.marginTop = '10px';

    // Obtener datos de conexiones del grafo
    const nodeData = knowledgeGraph[noteData.path];
    if (nodeData && nodeData.connections && nodeData.connections.length > 0) {
        nodeData.connections.sort((a, b) => b.strength - a.strength);

        // Mostrar las conexiones más fuertes
        const connectionsToShow = Math.min(nodeData.connections.length, 5);
        for (let i = 0; i < connectionsToShow; i++) {
            const connection = nodeData.connections[i];
            const targetNote = data.notes[connection.target];

            if (targetNote) {
                const connectionElement = document.createElement('div');
                connectionElement.style.marginBottom = '8px';
                connectionElement.style.padding = '5px';
                connectionElement.style.background = 'rgba(20, 25, 40, 0.5)';
                connectionElement.style.borderRadius = '5px';
                connectionElement.style.borderLeft = `3px solid ${getConnectionColor(connection.type)}`;

                const connectionType = document.createElement('span');
                connectionType.textContent = `${connection.type}: `;
                connectionType.style.color = '#00d4ff';
                connectionType.style.fontWeight = 'bold';

                const connectionTitle = document.createElement('span');
                connectionTitle.textContent = targetNote.title;
                connectionTitle.style.color = '#ccc';
                connectionTitle.style.cursor = 'pointer';
                connectionTitle.addEventListener('click', () => {
                    // Encontrar el nodo objetivo y mostrar su panel
                    const targetNode = knowledgeNodes.find(n => n.userData.path === connection.target);
                    if (targetNode) {
                        showKnowledgePanel(targetNode.userData);
                    }
                });

                const connectionStrength = document.createElement('span');
                connectionStrength.textContent = ` (${connection.strength.toFixed(1)})`;
                connectionStrength.style.color = '#666';
                connectionStrength.style.fontSize = '10px';

                connectionElement.appendChild(connectionType);
                connectionElement.appendChild(connectionTitle);
                connectionElement.appendChild(connectionStrength);

                connectionsDiv.appendChild(connectionElement);
            }
        }
    } else {
        const noConnections = document.createElement('div');
        noConnections.textContent = 'No hay relaciones definidas para esta nota.';
        noConnections.style.color = '#666';
        noConnections.style.fontStyle = 'italic';
        connectionsDiv.appendChild(noConnections);
    }

    // Botón para cerrar el panel
    const closeButton = document.createElement('div');
    closeButton.className = 'knowledge-panel-close';
    closeButton.style.position = 'absolute';
    closeButton.style.top = '10px';
    closeButton.style.right = '10px';
    closeButton.style.width = '24px';
    closeButton.style.height = '24px';
    closeButton.style.background = 'rgba(255, 51, 102, 0.2)';
    closeButton.style.border = '1px solid rgba(255, 51, 102, 0.5)';
    closeButton.style.borderRadius = '50%';
    closeButton.style.display = 'flex';
    closeButton.style.alignItems = 'center';
    closeButton.style.justifyContent = 'center';
    closeButton.style.color = '#ff3366';
    closeButton.style.fontSize = '16px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.zIndex = '10';
    closeButton.style.transition = 'all 0.2s ease';
    closeButton.innerHTML = '✕';

    closeButton.addEventListener('click', () => {
        closeKnowledgePanel();
    });

    // Añadir elementos al panel
    panelContent.appendChild(panelHeader);
    panelContent.appendChild(contentTitle);
    panelContent.appendChild(contentDiv);
    panelContent.appendChild(connectionsTitle);
    panelContent.appendChild(connectionsDiv);

    // Añadir el botón de cerrar al contenedor
    panelContainer.appendChild(closeButton);
    panelContainer.appendChild(panelContent);

    // Añadir el panel al cuerpo
    document.body.appendChild(panelContainer);

    // Posicionar el panel cerca del nodo clickeado
    const nodePosition = getNodeScreenPosition(noteData.node);
    if (nodePosition) {
        panelContainer.style.left = `${nodePosition.x + 20}px`;
        panelContainer.style.top = `${nodePosition.y - 100}px`;
    }

    // Mostrar el panel con animación
    setTimeout(() => {
        panelContainer.style.display = 'block';
    }, 10);

    // Guardar referencia al panel activo
    activeKnowledgePanel = {
        container: panelContainer,
        content: panelContent,
        noteData: noteData,
        closeButton: closeButton
    };

    // Cerrar el panel después de un tiempo
    setTimeout(() => {
        if (activeKnowledgePanel === panelContainer) {
            closeKnowledgePanel();
        }
    }, KNOWLEDGE_NODES_CONFIG.panelDuration);
}

// Función para obtener la posición de pantalla de un nodo
function getNodeScreenPosition(nodeData) {
    if (!nodeData || !nodeData.node) return null;

    const mesh = nodeData.node.mesh;
    if (!mesh) return null;

    const camera = window.threeCamera;
    const renderer = window.threeRenderer;

    // Convertir posición 3D a coordenadas de pantalla
    const vector = new THREE.Vector3();
    vector.copy(mesh.position);
    vector.project(camera);

    // Convertir a coordenadas de pantalla
    const widthHalf = renderer.domElement.width / 2;
    const heightHalf = renderer.domElement.height / 2;

    const x = (vector.x * widthHalf) + widthHalf;
    const y = -(vector.y * heightHalf) + heightHalf;

    return { x, y };
}

// Función para cerrar el panel de conocimiento
function closeKnowledgePanel() {
    if (activeKnowledgePanel) {
        activeKnowledgePanel.container.style.opacity = '0';
        activeKnowledgePanel.container.style.transform = 'translate(-50%, -50%) scale(0.9)';

        setTimeout(() => {
            if (activeKnowledgePanel) {
                document.body.removeChild(activeKnowledgePanel.container);
                activeKnowledgePanel = null;
            }
        }, 300);
    }
}

// Función para expandir un nodo
function expandKnowledgeNode(node) {
    if (node.userData.expanded) return;

    const originalSize = node.userData.originalSize;
    const targetSize = originalSize * 1.5;

    // Guardar el estado original
    node.userData.expanded = true;
    node.userData.originalScale = new THREE.Vector3(
        node.mesh.scale.x,
        node.mesh.scale.y,
        node.mesh.scale.z
    );

    // Animación de expansión
    let startTime = null;
    const duration = 300; // ms

    function animateExpand(timestamp) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Calcular escala intermedia
        const currentScale = node.userData.originalScale.clone();
        currentScale.multiplyScalar(1 + (targetSize/originalSize - 1) * progress);

        // Aplicar escala
        node.mesh.scale.copy(currentScale);

        // Actualizar brillo
        if (node.mesh.userData.glowMesh) {
            node.mesh.userData.glowMesh.scale.copy(currentScale);
            node.mesh.userData.glowMesh.scale.multiplyScalar(1.2);
        }

        // Continuar la animación si no ha terminado
        if (progress < 1) {
            node.userData.expandAnimationId = requestAnimationFrame(animateExpand);
        } else {
            node.userData.expanding = false;
        }
    }

    node.userData.expandAnimationId = requestAnimationFrame(animateExpand);
}

// Función para contraer un nodo
function collapseKnowledgeNode(node) {
    if (!node.userData.expanded) return;

    const originalScale = node.userData.originalScale;

    // Animación de contracción
    let startTime = null;
    const duration = 300; // ms

    function animateCollapse(timestamp) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Calcular escala intermedia
        const currentScale = new THREE.Vector3(
            originalScale.x + (node.mesh.scale.x - originalScale.x) * (1 - progress),
            originalScale.y + (node.mesh.scale.y - originalScale.y) * (1 - progress),
            originalScale.z + (node.mesh.scale.z - originalScale.z) * (1 - progress)
        );

        // Aplicar escala
        node.mesh.scale.copy(currentScale);

        // Actualizar brillo
        if (node.mesh.userData.glowMesh) {
            node.mesh.userData.glowMesh.scale.copy(currentScale);
            node.mesh.userData.glowMesh.scale.multiplyScalar(1.2);
        }

        // Continuar la animación si no ha terminado
        if (progress < 1) {
            node.userData.expandAnimationId = requestAnimationFrame(animateCollapse);
        } else {
            node.userData.expanded = false;
            node.userData.expanding = false;
        }
    }

    node.userData.expandAnimationId = requestAnimationFrame(animateCollapse);
}

// Función para obtener el color de una conexión por tipo
function getConnectionColor(type) {
    const config = KNOWLEDGE_NODES_CONFIG.connectionTypes[type] || {
        color: 0x8888ff
    };
    return config.color;
}

// Función para actualizar todos los nodos y conexiones
function updateKnowledgeNodes() {
    const currentTime = performance.now();
    const deltaTime = currentTime - lastUpdateTime;
    lastUpdateTime = currentTime;

    // Actualizar todos los nodos
    knowledgeNodes.forEach(node => {
        node.update();

        // Actualizar brillo si existe
        if (node.mesh.userData.glowMesh) {
            node.mesh.userData.updateGlow();
        }

        // Aplicar efecto de amenaza si el nodo está en amenaza
        applyThreatEffect(node, deltaTime);
    });

    // Actualizar líneas de conexión cada frame
    updateConnectionLines();

    // Actualizar restricciones físicas
    updatePhysicsConstraints();
}

// Función para actualizar líneas de conexión
function updateConnectionLines() {
    if (!KNOWLEDGE_NODES_CONFIG.connectionLineMesh) return;

    // Actualizar todas las líneas de conexión
    connectionLineMeshes.forEach(line => {
        if (line.userData.visible) {
            line.update();
        }
    });
}

// Función para actualizar restricciones físicas
function updatePhysicsConstraints() {
    if (!KNOWLEDGE_NODES_CONFIG.physicsConstraints || !window.CANNON) return;

    // Actualizar restricciones físicas
    KNOWLEDGE_NODES_CONFIG.distanceConstraints.forEach(constraintData => {
        // Verificar que ambos nodos aún existan
        if (constraintData.node1 && constraintData.node2 &&
            constraintData.node1.body && constraintData.node2.body) {

            // Calcular distancia actual
            const currentDistance = constraintData.node1.mesh.position.distanceTo(
                constraintData.node2.mesh.position
            );

            // Actualizar la longitud de reposo de la restricción
            // (la restricción se actualiza automáticamente en el paso de física)
        }
    });
}

// Función para iniciar la animación de actualización
function startConnectionAnimation() {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }

    function animate() {
        updateKnowledgeNodes();
        animationFrameId = requestAnimationFrame(animate);
    }

    animate();
}

// Función para detener la animación
function stopConnectionAnimation() {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
}

// Función para aplicar efecto de amenaza a un nodo
function applyThreatEffect(node, deltaTime) {
    if (!KNOWLEDGE_NODES_CONFIG.pulseEffect) return;

    const nodeData = node.userData;
    const isThreatNode = threatActiveNodes.includes(nodeData.path);

    // Si el nodo está en amenaza, aplicar efecto de pulso
    if (isThreatNode) {
        // Cambiar color a rojo de amenaza
        const threatColor = KNOWLEDGE_NODES_CONFIG.threatColor;
        if (node.mesh.material.color.getHex() !== threatColor) {
            node.mesh.material.color.setHex(threatColor);
            node.mesh.userData.originalColor = threatColor;
        }

        // Aplicar efecto de pulso
        if (node.userData.pulseAnimation) {
            const pulseProgress = (performance.now() - node.userData.pulseStartTime) /
                                  KNOWLEDGE_NODES_CONFIG.pulseDuration;

            if (pulseProgress < 1) {
                // Calcular escala de pulso
                const pulseScale = 1 + KNOWLEDGE_NODES_CONFIG.pulseIntensity *
                    Math.sin(pulseProgress * Math.PI);

                // Aplicar escala de pulso
                node.mesh.scale.set(
                    node.userData.originalScale.x * pulseScale,
                    node.userData.originalScale.y * pulseScale,
                    node.userData.originalScale.z * pulseScale
                );

                // Actualizar brillo si existe
                if (node.mesh.userData.glowMesh) {
                    node.mesh.userData.glowMesh.scale.set(
                        node.mesh.scale.x * 1.2,
                        node.mesh.scale.y * 1.2,
                        node.mesh.scale.z * 1.2
                    );
                }
            } else {
                // Restaurar escala original
                node.mesh.scale.copy(node.userData.originalScale);
                if (node.mesh.userData.glowMesh) {
                    node.mesh.userData.glowMesh.scale.copy(node.userData.originalScale);
                    node.mesh.userData.glowMesh.scale.multiplyScalar(1.2);
                }

                // Reiniciar animación de pulso
                node.userData.pulseStartTime = performance.now();
            }
        } else {
            // Iniciar animación de pulso
            node.userData.pulseStartTime = performance.now();
            node.userData.pulseAnimation = true;
        }
    } else {
        // Restaurar color original si no está en amenaza
        if (node.mesh.material.color.getHex() !== node.userData.originalColor) {
            node.mesh.material.color.setHex(node.userData.originalColor);
        }

        // Detener animación de pulso
        if (node.userData.pulseAnimation) {
            node.mesh.scale.copy(node.userData.originalScale);
            if (node.mesh.userData.glowMesh) {
                node.mesh.userData.glowMesh.scale.copy(node.userData.originalScale);
                node.mesh.userData.glowMesh.scale.multiplyScalar(1.2);
            }
            node.userData.pulseAnimation = false;
        }
    }
}

// Función para actualizar el estado de amenaza de un nodo
function updateThreatState(nodePath, isThreat) {
    if (isThreat) {
        if (!threatActiveNodes.includes(nodePath)) {
            threatActiveNodes.push(nodePath);

            // Encontrar el nodo y aplicar efecto de amenaza
            const node = knowledgeNodes.find(n => n.userData.path === nodePath);
            if (node) {
                // Cambiar color a rojo de amenaza
                node.mesh.material.color.setHex(KNOWLEDGE_NODES_CONFIG.threatColor);
                node.mesh.userData.originalColor = KNOWLEDGE_NODES_CONFIG.threatColor;

                // Iniciar efecto de pulso
                node.userData.pulseStartTime = performance.now();
                node.userData.pulseAnimation = true;

                // Añadir mensaje al log
                addLogEntry(`🚨 AMENZA DETECTADA: ${node.userData.title}`, 'critical');
            }

            // Propagar la amenaza a nodos relacionados
            propagateThreat(nodePath);
        }
    } else {
        const index = threatActiveNodes.indexOf(nodePath);
        if (index !== -1) {
            threatActiveNodes.splice(index, 1);

            // Encontrar el nodo y restaurar estado normal
            const node = knowledgeNodes.find(n => n.userData.path === nodePath);
            if (node) {
                // Restaurar color original
                node.mesh.material.color.setHex(node.userData.originalColor);

                // Detener efecto de pulso
                if (node.userData.pulseAnimation) {
                    node.mesh.scale.copy(node.userData.originalScale);
                    if (node.mesh.userData.glowMesh) {
                        node.mesh.userData.glowMesh.scale.copy(node.userData.originalScale);
                        node.mesh.userData.glowMesh.scale.multiplyScalar(1.2);
                    }
                    node.userData.pulseAnimation = false;
                }

                // Añadir mensaje al log
                addLogEntry(`🟢 AMENZA RESUELTA: ${node.userData.title}`, 'success');
            }
        }
    }
}

// Función para propagar una amenaza a nodos relacionados
function propagateThreat(nodePath, depth = 0, maxDepth = 2) {
    if (depth >= maxDepth) return;

    const nodeData = knowledgeGraph[nodePath];
    if (!nodeData || !nodeData.connections) return;

    // Propagar amenaza a nodos directamente conectados
    nodeData.connections.forEach(connection => {
        const targetPath = connection.target;
        const targetNodeData = knowledgeGraph[targetPath];

        if (targetNodeData && !threatActiveNodes.includes(targetPath)) {
            // Aplicar amenaza al nodo objetivo
            updateThreatState(targetPath, true);

            // Recursivamente propagar a nodos relacionados
            propagateThreat(targetPath, depth + 1, maxDepth);
        }
    });
}

// Función para filtrar nodos por búsqueda
function filterNodesBySearch(query) {
    if (!query || query.trim() === '') {
        // Restaurar todos los nodos si no hay búsqueda
        resetNodeVisibility();
        return;
    }

    // Buscar términos en el índice de búsqueda
    const searchTerms = query.toLowerCase().split(' ');
    const relevantNodes = new Set();

    // Buscar en el índice de términos
    for (const term of searchTerms) {
        if (KNOWLEDGE_NODES_CONFIG.search_index.terms[term]) {
            KNOWLEDGE_NODES_CONFIG.search_index.terms[term].nodes.forEach(nodePath => {
                relevantNodes.add(nodePath);
            });
        }
    }

    // Si no se encontraron términos exactos, buscar en el contenido
    if (relevantNodes.size === 0) {
        for (const [nodePath, nodeData] of Object.entries(KNOWLEDGE_NODES_CONFIG.notes || {})) {
            const content = (nodeData.content || '').toLowerCase();
            for (const term of searchTerms) {
                if (content.includes(term)) {
                    relevantNodes.add(nodePath);
                    break;
                }
            }
        }
    }

    // Aplicar filtrado a los nodos
    knowledgeNodes.forEach(node => {
        const nodePath = node.userData.path;
        const isRelevant = relevantNodes.has(nodePath);

        // Aplicar opacidad según relevancia
        if (isRelevant) {
            node.mesh.material.opacity = KNOWLEDGE_NODES_CONFIG.searchHighlightOpacity;
            node.mesh.material.transparent = true;
            node.mesh.userData.isHighlighted = true;
        } else {
            node.mesh.material.opacity = KNOWLEDGE_NODES_CONFIG.searchFadeOpacity;
            node.mesh.material.transparent = true;
            node.mesh.userData.isHighlighted = false;
        }

        // Guardar estado para restauración
        node.userData.originalOpacity = isRelevant ?
            1 : KNOWLEDGE_NODES_CONFIG.searchHighlightOpacity;
    });

    // Actualizar visibilidad de conexiones
    updateConnectionVisibility(relevantNodes);

    // Guardar nodos destacados para referencia
    searchHighlightedNodes = Array.from(relevantNodes);

    console.log(`🔍 Filtrado aplicado: ${relevantNodes.size} nodos relevantes de ${knowledgeNodes.length} totales`);
}

// Función para restaurar la visibilidad de todos los nodos
function resetNodeVisibility() {
    knowledgeNodes.forEach(node => {
        // Restaurar opacidad original
        node.mesh.material.opacity = 1;
        node.mesh.material.transparent = false;
        node.mesh.userData.isHighlighted = false;

        // Restaurar color original si estaba en amenaza
        if (threatActiveNodes.includes(node.userData.path)) {
            node.mesh.material.color.setHex(KNOWLEDGE_NODES_CONFIG.threatColor);
        } else {
            node.mesh.material.color.setHex(node.userData.originalColor);
        }
    });

    // Restaurar visibilidad de todas las conexiones
    updateConnectionVisibility(new Set(Object.keys(knowledgeGraph)));

    // Limpiar nodos destacados
    searchHighlightedNodes = [];
}

// Función para actualizar visibilidad de conexiones
function updateConnectionVisibility(relevantNodes) {
    if (!connectionLineMeshes) return;

    connectionLineMeshes.forEach(line => {
        const node1Path = line.userData.node1.userData.path;
        const node2Path = line.userData.node2.userData.path;

        // Verificar si ambos nodos son relevantes o si al menos uno lo es
        const isRelevant = relevantNodes.has(node1Path) || relevantNodes.has(node2Path);

        // Mostrar u ocultar la conexión según relevancia
        line.userData.visible = isRelevant;
    });
}

// Función para añadir entradas al log (simulada)
function addLogEntry(message, type) {
    // En una implementación real, esto añadiría al log del panel de control
    console.log(`[KNOWLEDGE_NODES] ${type.toUpperCase()}: ${message}`);

    // Notificar al sistema principal si existe
    if (window.AgentControl) {
        window.AgentControl.addLogEntry(message, type);
    }
}

// Función para inicializar los nodos de conocimiento
function initKnowledgeNodes() {
    // Verificar que el motor de física esté disponible
    if (!window.PhysicsUI || !window.threeScene) {
        console.error("PhysicsUI no disponible. Esperando inicialización...");
        setTimeout(initKnowledgeNodes, 1000);
        return;
    }

    // Cargar la base de conocimiento
    loadKnowledgeBase().then(success => {
        if (success) {
            // Registrar función de actualización en el motor de física
            window.PhysicsUI.updatePhysics = function() {
                updateKnowledgeNodes();
            };

            // Exponer funciones públicas
            window.KnowledgeNodes = {
                init: initKnowledgeNodes,
                load: loadKnowledgeBase,
                createNode: createKnowledgeNode,
                showPanel: showKnowledgePanel,
                closePanel: closeKnowledgePanel,
                expandNode: expandKnowledgeNode,
                collapseNode: collapseKnowledgeNode,
                update: updateKnowledgeNodes,
                filterBySearch: filterNodesBySearch,
                resetVisibility: resetNodeVisibility,
                updateThreatState: updateThreatState,
                getNodeByPath: function(path) {
                    return knowledgeNodes.find(node => node.userData.path === path);
                },
                getGraph: function() {
                    return { ...knowledgeGraph };
                },
                getConnectionLines: function() {
                    return connectionLineMeshes;
                },
                getDistanceConstraints: function() {
                    return KNOWLEDGE_NODES_CONFIG.distanceConstraints;
                },
                config: KNOWLEDGE_NODES_CONFIG
            };

            console.log("🎮 Nodos de conocimiento inicializados con éxito");
            console.log(`   - ${knowledgeNodes.length} nodos creados`);
            console.log(`   - ${calculateTotalConnections()} conexiones establecidas`);
            console.log(`   - ${KNOWLEDGE_NODES_CONFIG.distanceConstraints.length} restricciones físicas activas`);
        } else {
            // Intentar nuevamente en 5 segundos
            setTimeout(initKnowledgeNodes, 5000);
        }
    });
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si Three.js y Cannon-es están disponibles
    if (window.THREE && window.CANNON) {
        initKnowledgeNodes();
    } else {
        console.warn("Esperando carga de Three.js y Cannon-es para inicializar nodos de conocimiento...");
        const checkInterval = setInterval(() => {
            if (window.THREE && window.CANNON) {
                clearInterval(checkInterval);
                initKnowledgeNodes();
            }
        }, 100);
    }
});

// Exportar funciones para uso externo
window.KnowledgeNodes = window.KnowledgeNodes || {};