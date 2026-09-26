/**
 * physics_ui.js - Motor de física 3D para el Dashboard AURA
 * Usa Three.js + Cannon-es para crear un entorno Antigravity
 * Efectos de física realista con arrastre por resorte y gravedad ajustable
 */

// Configuración global del motor de física (estilo Antigravity)
const PHYSICS_CONFIG = {
    gravity: 0.3,          // Gravedad reducida para efecto "antigravedad"
    damping: 0.2,          // Baja amortiguación para mayor inercia
    massMultiplier: 0.3,   // Objetos más ligeros para efecto fluido
    friction: 0.1,         // Baja fricción para movimiento suave
    restitution: 0.8,      // Alto rebote para efecto "flotante"
    springConstant: 0.15,  // Constante de resorte para arrastre
    dragForce: 0.05,       // Fuerza de arrastre para seguir el cursor
    maxVelocity: 5.0,      // Velocidad máxima para evitar objetos demasiado rápidos
    worldScale: 1.5        // Escala del mundo para mejor visualización
};

// Variables globales del motor
let physicsWorld;
let threeScene;
let threeCamera;
let threeRenderer;
let physicsObjects = [];
let animationId = null;
let canvasContainer = null;
let dragControls = null;
let mouse = { x: 0, y: 0 };
let windowHalf = { width: window.innerWidth / 2, height: window.innerHeight / 2 };
let selectedObject = null;
let dragOffset = { x: 0, y: 0, z: 0 };
let springForce = { x: 0, y: 0, z: 0 };
let isDragging = false;

// Inicializar el motor de física
function initPhysicsEngine() {
    // Verificar que Three.js y Cannon-es estén disponibles
    if (!window.THREE || !window.CANNON) {
        console.error("Error: Three.js o Cannon-es no están cargados");
        return false;
    }

    // Crear mundo físico con Cannon-es (configuración Antigravity)
    physicsWorld = new CANNON.World();
    physicsWorld.gravity.set(0, -PHYSICS_CONFIG.gravity, 0);
    physicsWorld.broadphase = new CANNON.NaiveBroadphase();
    physicsWorld.solver.iterations = 10;

    // Crear escena Three.js
    threeScene = new THREE.Scene();
    threeScene.background = new THREE.Color(0x0a0f1e);

    // Crear cámara con perspectiva ajustada para Antigravity
    threeCamera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    threeCamera.position.set(0, 0, 80);
    threeCamera.lookAt(0, 0, 0);

    // Crear renderer con efectos de profundidad
    threeRenderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        logarithmicDepthBuffer: true
    });
    threeRenderer.setSize(window.innerWidth, window.innerHeight);
    threeRenderer.setPixelRatio(window.devicePixelRatio);
    threeRenderer.shadowMap.enabled = true;
    threeRenderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Crear contenedor para el canvas con estilo Antigravity
    canvasContainer = document.createElement('div');
    canvasContainer.id = 'physics-ui-canvas';
    canvasContainer.style.position = 'fixed';
    canvasContainer.style.top = '0';
    canvasContainer.style.left = '0';
    canvasContainer.style.width = '100%';
    canvasContainer.style.height = '100%';
    canvasContainer.style.zIndex = '999';
    canvasContainer.style.pointerEvents = 'none';
    canvasContainer.style.overflow = 'hidden';
    canvasContainer.style.background = 'linear-gradient(135deg, rgba(10, 15, 26, 0.8), rgba(0, 0, 0, 0.6))';

    // Añadir renderer al contenedor
    canvasContainer.appendChild(threeRenderer.domElement);

    // Añadir luces con efecto Antigravity
    const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
    threeScene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
    directionalLight.position.set(1, 1, 1);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    threeScene.add(directionalLight);

    // Añadir luces ambientales para efecto "espacio"
    const light1 = new THREE.PointLight(0x00d4ff, 0.5, 100);
    light1.position.set(-30, 20, 30);
    threeScene.add(light1);

    const light2 = new THREE.PointLight(0xff3366, 0.5, 100);
    light2.position.set(30, -20, -30);
    threeScene.add(light2);

    // Añadir suelo (plano invisible) con efecto de profundidad
    const groundGeometry = new THREE.PlaneGeometry(200, 200);
    const groundMaterial = new THREE.MeshStandardMaterial({
        color: 0x1a1a2e,
        side: THREE.DoubleSide,
        roughness: 0.8,
        metalness: 0.2
    });
    const groundMesh = new THREE.Mesh(groundGeometry, groundMaterial);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.receiveShadow = true;
    threeScene.add(groundMesh);

    // Crear cuerpo físico para el suelo
    const groundBody = new CANNON.Body({
        mass: 0,
        shape: new CANNON.Plane(),
        position: new CANNON.Vec3(0, 0, 0)
    });
    physicsWorld.addBody(groundBody);

    // Configurar controles de arrastre con efecto de resorte
    setupDragControls();

    // Manejar redimensionamiento de ventana
    window.addEventListener('resize', onWindowResize);

    // Iniciar animación
    startAnimation();

    console.log("🚀 PHYSICS ENGINE (ANTIGRAVITY) INICIALIZADO");
    return true;
}

// Configurar controles de arrastre con efecto de resorte
function setupDragControls() {
    // Crear controles de arrastre personalizados
    dragControls = {
        active: false,
        object: null,
        offset: { x: 0, y: 0, z: 0 },
        spring: { x: 0, y: 0, z: 0 },
        target: { x: 0, y: 0, z: 0 },
        velocity: { x: 0, y: 0, z: 0 }
    };

    // Manejar eventos de mouse
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mouseup', onMouseUp);
    document.addEventListener('mouseleave', onMouseUp);

    // Función para manejar movimiento del mouse
    function onMouseMove(event) {
        mouse.x = (event.clientX - windowHalf.width) * 2;
        mouse.y = (event.clientY - windowHalf.height) * 2;

        if (dragControls.active) {
            // Calcular posición del cursor en coordenadas 3D
            const cursorX = (mouse.x / windowHalf.width) * 100 - 50;
            const cursorY = -(mouse.y / windowHalf.height) * 100 + 50;

            // Aplicar efecto de resorte (spring physics)
            dragControls.spring.x = cursorX - dragControls.offset.x;
            dragControls.spring.y = cursorY - dragControls.offset.y;

            // Aplicar fuerza al objeto
            const body = dragControls.object.userData.physicsBody;
            body.force.set(
                dragControls.spring.x * PHYSICS_CONFIG.springConstant,
                dragControls.spring.y * PHYSICS_CONFIG.springConstant,
                0
            );

            // Limitar velocidad para evitar objetos demasiado rápidos
            const currentVelocity = body.velocity;
            const speed = Math.sqrt(
                currentVelocity.x * currentVelocity.x +
                currentVelocity.y * currentVelocity.y +
                currentVelocity.z * currentVelocity.z
            );

            if (speed > PHYSICS_CONFIG.maxVelocity) {
                const factor = PHYSICS_CONFIG.maxVelocity / speed;
                body.velocity.set(
                    currentVelocity.x * factor,
                    currentVelocity.y * factor,
                    currentVelocity.z * factor
                );
            }
        }
    }

    // Función para manejar clic del mouse
    function onMouseDown(event) {
        if (event.button !== 0) return; // Solo botón izquierdo

        // Verificar si se hizo clic en un objeto físico
        const raycaster = new THREE.Raycaster();
        const mouseVector = new THREE.Vector2();
        mouseVector.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouseVector.y = -(event.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouseVector, threeCamera);
        const intersects = raycaster.intersectObjects(
            physicsObjects.map(obj => obj.mesh)
        );

        if (intersects.length > 0) {
            const object = intersects[0].object;
            selectedObject = object;

            // Guardar offset para efecto de resorte
            const body = object.userData.physicsBody;
            dragControls.offset = {
                x: body.position.x,
                y: body.position.y,
                z: body.position.z
            };

            // Detener el objeto antes de arrastrar
            body.velocity.set(0, 0, 0);
            body.angularVelocity.set(0, 0, 0);

            dragControls.active = true;
            isDragging = true;

            // Disparar evento de clic en el objeto
            if (object.userData.onClick) {
                object.userData.onClick();
            }
        }
    }

    // Función para manejar liberación del mouse
    function onMouseUp(event) {
        if (!dragControls.active) return;

        // Liberar el objeto con efecto de inercia
        const body = dragControls.object.userData.physicsBody;
        body.force.set(0, 0, 0);

        // Aplicar un pequeño impulso aleatorio para efecto de inercia
        body.velocity.set(
            (Math.random() - 0.5) * 2,
            (Math.random() - 0.5) * 2,
            0
        );

        dragControls.active = false;
        isDragging = false;
        selectedObject = null;
    }
}

// Crear un objeto físico con propiedades personalizables
function createPhysicsObject(options = {}) {
    const defaults = {
        mass: 1,
        width: 5,
        height: 5,
        depth: 5,
        color: 0x00d4ff,
        position: { x: 0, y: 20, z: 0 },
        velocity: { x: 0, y: 0, z: 0 },
        angularVelocity: { x: 0, y: 0, z: 0 },
        userData: {},
        isDraggable: true,
        type: 'box'
    };

    const config = { ...defaults, ...options };

    // Crear cuerpo físico en Cannon
    let shape;
    if (config.type === 'box') {
        shape = new CANNON.Box(new CANNON.Vec3(
            config.width / 2,
            config.height / 2,
            config.depth / 2
        ));
    } else if (config.type === 'sphere') {
        shape = new CANNON.Sphere(config.width / 2);
    } else {
        shape = new CANNON.Box(new CANNON.Vec3(
            config.width / 2,
            config.height / 2,
            config.depth / 2
        ));
    }

    const body = new CANNON.Body({
        mass: config.mass * PHYSICS_CONFIG.massMultiplier,
        shape: shape,
        position: new CANNON.Vec3(
            config.position.x,
            config.position.y,
            config.position.z
        ),
        velocity: new CANNON.Vec3(
            config.velocity.x,
            config.velocity.y,
            config.velocity.z
        ),
        angularVelocity: new CANNON.Vec3(
            config.angularVelocity.x,
            config.angularVelocity.y,
            config.angularVelocity.z
        ),
        linearDamping: PHYSICS_CONFIG.damping,
        angularDamping: PHYSICS_CONFIG.damping,
        material: new CANNON.Material({
            friction: PHYSICS_CONFIG.friction,
            restitution: PHYSICS_CONFIG.restitution
        })
    });

    // Crear malla en Three.js con materiales Antigravity
    let geometry, material;

    if (config.type === 'box') {
        geometry = new THREE.BoxGeometry(
            config.width,
            config.height,
            config.depth
        );

        material = new THREE.MeshStandardMaterial({
            color: config.color,
            metalness: 0.4,
            roughness: 0.6,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide,
            envMapIntensity: 0.5
        });
    } else if (config.type === 'sphere') {
        geometry = new THREE.SphereGeometry(
            config.width / 2,
            32,
            32
        );

        material = new THREE.MeshStandardMaterial({
            color: config.color,
            metalness: 0.3,
            roughness: 0.7,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide
        });
    } else {
        geometry = new THREE.BoxGeometry(
            config.width,
            config.height,
            config.depth
        );

        material = new THREE.MeshStandardMaterial({
            color: config.color,
            metalness: 0.4,
            roughness: 0.6,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide
        });
    }

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = {
        physicsBody: body,
        originalConfig: config,
        isDraggable: config.isDraggable || false
    };

    // Añadir cuerpo físico al mundo
    physicsWorld.addBody(body);

    // Añadir malla a la escena
    threeScene.add(mesh);

    // Guardar referencia al objeto
    const physicsObject = {
        mesh: mesh,
        body: body,
        config: config,
        update: function() {
            if (body.position) mesh.position.copy(body.position);
            if (body.quaternion) mesh.quaternion.copy(body.quaternion);
        }
    };

    physicsObjects.push(physicsObject);
    return physicsObject;
}

// Crear un cubo de prueba con efecto Antigravity
function createTestCube() {
    return createPhysicsObject({
        mass: 1.5,
        width: 8,
        height: 8,
        depth: 8,
        color: 0xff3366, // Rosa para destacar (estilo Antigravity)
        position: { x: 0, y: 40, z: 0 }, // Posición inicial más alta
        userData: {
            type: 'test_cube',
            description: 'Cubo de prueba con efecto Antigravity',
            draggable: true
        }
    });
}

// Crear un objeto con contenido HTML (para integrar con el dashboard)
function createHtmlObject(htmlElement, options = {}) {
    const defaults = {
        width: 10,
        height: 6,
        depth: 0.5,
        color: 0x00d4ff,
        position: { x: 0, y: 30, z: 0 },
        isDraggable: true,
        type: 'html'
    };

    const config = { ...defaults, ...options };

    // Crear cuerpo físico plano para el objeto HTML
    const shape = new CANNON.Box(new CANNON.Vec3(
        config.width / 2,
        config.height / 2,
        config.depth / 2
    ));

    const body = new CANNON.Body({
        mass: 0.1 * PHYSICS_CONFIG.massMultiplier, // Masa muy baja para efecto "flotante"
        shape: shape,
        position: new CANNON.Vec3(
            config.position.x,
            config.position.y,
            config.position.z
        ),
        linearDamping: PHYSICS_CONFIG.damping * 2, // Más amortiguación para efecto estable
        angularDamping: PHYSICS_CONFIG.damping * 2,
        material: new CANNON.Material({
            friction: PHYSICS_CONFIG.friction * 0.5,
            restitution: PHYSICS_CONFIG.restitution * 0.8
        })
    });

    // Crear malla con material transparente para mostrar el HTML
    const geometry = new THREE.BoxGeometry(
        config.width,
        config.height,
        config.depth
    );

    const material = new THREE.MeshBasicMaterial({
        color: config.color,
        transparent: true,
        opacity: 0.1,
        side: THREE.DoubleSide,
        depthTest: false,
        depthWrite: false
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = false;
    mesh.receiveShadow = false;
    mesh.userData = {
        physicsBody: body,
        originalConfig: config,
        isDraggable: config.isDraggable,
        htmlElement: htmlElement,
        type: 'html'
    };

    // Añadir cuerpo físico al mundo
    physicsWorld.addBody(body);

    // Añadir malla a la escena
    threeScene.add(mesh);

    // Guardar referencia al objeto
    const physicsObject = {
        mesh: mesh,
        body: body,
        config: config,
        htmlElement: htmlElement,
        update: function() {
            if (body.position) {
                mesh.position.copy(body.position);
            }
            if (body.quaternion) {
                mesh.quaternion.copy(body.quaternion);
            }
        }
    };

    physicsObjects.push(physicsObject);
    return physicsObject;
}

// Animación principal del motor de física con efectos Antigravity
function animate() {
    animationId = requestAnimationFrame(animate);

    // Actualizar física
    const timeStep = 1/60;
    physicsWorld.step(timeStep);

    // Actualizar objetos en la escena
    physicsObjects.forEach(object => {
        object.update();

        // Actualizar posición de elementos HTML si existen
        if (object.htmlElement && object.mesh) {
            const pos = object.mesh.position;
            const scale = PHYSICS_CONFIG.worldScale;

            // Aplicar transformación 3D al elemento HTML
            object.htmlElement.style.transform = `
                translate(${pos.x * scale}px, ${-pos.y * scale + window.innerHeight * 0.4}px, 0)
                scale(${scale * 0.3})
            `;

            // Aplicar rotación para efecto 3D
            object.htmlElement.style.transform += `
                rotateX(${pos.y * 0.5}deg)
                rotateY(${pos.x * 0.3}deg)
            `;

            // Aplicar efecto de opacidad según la altura
            const opacity = Math.max(0.3, 1 - Math.abs(pos.y) * 0.01);
            object.htmlElement.style.opacity = opacity;
        }
    });

    // Renderizar
    threeRenderer.render(threeScene, threeCamera);
}

// Manejar redimensionamiento de ventana
function onWindowResize() {
    windowHalf.width = window.innerWidth / 2;
    windowHalf.height = window.innerHeight / 2;

    threeCamera.aspect = window.innerWidth / window.innerHeight;
    threeCamera.updateProjectionMatrix();
    threeRenderer.setSize(window.innerWidth, window.innerHeight);
}

// Iniciar la animación
function startAnimation() {
    if (animationId) {
        cancelAnimationFrame(animationId);
    }
    animate();
}

// Detener la animación
function stopAnimation() {
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
}

// Añadir el canvas al DOM
function mountPhysicsCanvas() {
    if (!canvasContainer) return false;

    // Verificar si el canvas ya está montado
    const existingCanvas = document.getElementById('physics-ui-canvas');
    if (existingCanvas) {
        console.log("⚠️  El canvas de física ya está montado");
        return true;
    }

    // Añadir el canvas al body (detrás de otros elementos)
    document.body.insertBefore(canvasContainer, document.body.firstChild);
    return true;
}

// Inicializar el motor de física completo con efectos Antigravity
function initPhysicsUI() {
    // Verificar dependencias
    if (!window.THREE || !window.CANNON) {
        console.error("Error: Three.js o Cannon-es no están cargados");
        return false;
    }

    // Inicializar el motor
    const success = initPhysicsEngine();

    if (success) {
        // Crear cubo de prueba con efecto Antigravity
        createTestCube();

        // Montar el canvas
        mountPhysicsCanvas();

        console.log("🎮 PHYSICS UI ENGINE (ANTIGRAVITY) LISTO");
        console.log("   - Motor de física con efectos Antigravity inicializado");
        console.log("   - Cubo de prueba creado con efecto de flotación");
        console.log("   - Sistema de arrastre con efecto de resorte implementado");
        console.log("   - Canvas montado en el DOM con z-index 999");

        return true;
    }

    return false;
}

// Exportar funciones para uso externo
window.PhysicsUI = {
    init: initPhysicsUI,
    createObject: createPhysicsObject,
    createHtmlObject: createHtmlObject,
    config: PHYSICS_CONFIG,
    mountCanvas: mountPhysicsCanvas,
    stop: stopAnimation,
    updatePhysics: function() {
        if (animationId) {
            cancelAnimationFrame(animationId);
            animate();
        }

        // Actualizar nodos de conocimiento si existen
        if (window.KnowledgeNodes) {
            window.KnowledgeNodes.update();
        }
    }
};

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si Three.js y Cannon-es están disponibles
    if (window.THREE && window.CANNON) {
        initPhysicsUI();

        // Inicializar nodos de conocimiento después de que el motor de física esté listo
        setTimeout(() => {
            if (window.KnowledgeNodes) {
                window.KnowledgeNodes.init();
            } else {
                // Cargar el módulo de nodos de conocimiento
                const script = document.createElement('script');
                script.src = '/ui_engine/knowledge_nodes.js';
                script.onload = () => {
                    if (window.KnowledgeNodes) {
                        window.KnowledgeNodes.init();
                    }
                };
                document.body.appendChild(script);
            }
        }, 1000);
    } else {
        console.warn("Esperando carga de Three.js y Cannon-es...");
        const checkInterval = setInterval(() => {
            if (window.THREE && window.CANNON) {
                clearInterval(checkInterval);
                initPhysicsUI();

                // Inicializar nodos de conocimiento después de que el motor de física esté listo
                setTimeout(() => {
                    if (window.KnowledgeNodes) {
                        window.KnowledgeNodes.init();
                    } else {
                        // Cargar el módulo de nodos de conocimiento
                        const script = document.createElement('script');
                        script.src = '/ui_engine/knowledge_nodes.js';
                        script.onload = () => {
                            if (window.KnowledgeNodes) {
                                window.KnowledgeNodes.init();
                            }
                        };
                        document.body.appendChild(script);
                    }
                }, 1000);
            }
        }, 100);
    }
});