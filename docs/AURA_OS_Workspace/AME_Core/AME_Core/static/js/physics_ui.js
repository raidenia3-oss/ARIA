/**
 * physics_ui.js - Módulo de física 3D para el Dashboard Antigravity
 * Usa Three.js + Cannon-es para crear un entorno con física realista
 * Inspiración: Estilo Antigravity (fluido, 3D, con peso)
 */

// Configuración global
const PHYSICS_CONFIG = {
    gravity: 0.5,          // Gravedad (ajustada para efecto "antigravedad")
    damping: 0.5,           // Amortiguación (efecto de inercia)
    springConstant: 0.2,   // Constante de resorte (para efecto de arrastre)
    massMultiplier: 0.1,    // Multiplicador de masa (objetos más ligeros)
    friction: 0.1,         // Fricción
    restitution: 0.7        // Coeficiente de restitución (rebote)
};

// Inicialización del mundo físico
let physicsWorld;
let threeScene;
let threeCamera;
let threeRenderer;
let controls;
let rafId;
let dragObject = null;
let dragOffset = { x: 0, y: 0 };
let mouse = { x: 0, y: 0 };
let windowHalf = { width: window.innerWidth / 2, height: window.innerHeight / 2 };

// Inicializar el mundo físico con Cannon-es
function initPhysicsWorld() {
    // Crear mundo físico
    physicsWorld = new CANNON.World();
    physicsWorld.gravity.set(0, 0, -PHYSICS_CONFIG.gravity); // Gravedad hacia arriba (antigravedad)
    physicsWorld.broadphase = new CANNON.NaiveBroadphase();
    physicsWorld.solver.iterations = 10;

    // Crear escena Three.js
    threeScene = new THREE.Scene();
    threeScene.background = new THREE.Color(0x0a0f1e); // Fondo oscuro

    // Crear cámara
    threeCamera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    threeCamera.position.set(0, 0, 50);
    threeCamera.lookAt(0, 0, 0);

    // Crear renderer
    threeRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    threeRenderer.setSize(window.innerWidth, window.innerHeight);
    threeRenderer.setPixelRatio(window.devicePixelRatio);
    threeRenderer.shadowMap.enabled = true;

    // Añadir renderer al DOM
    const canvasContainer = document.createElement('div');
    canvasContainer.id = 'physics-canvas-container';
    canvasContainer.style.position = 'fixed';
    canvasContainer.style.top = '0';
    canvasContainer.style.left = '0';
    canvasContainer.style.width = '100%';
    canvasContainer.style.height = '100%';
    canvasContainer.style.zIndex = '1000';
    canvasContainer.style.pointerEvents = 'none';
    document.body.appendChild(canvasContainer);
    canvasContainer.appendChild(threeRenderer.domElement);

    // Añadir luces
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    threeScene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(1, 1, 1);
    directionalLight.castShadow = true;
    threeScene.add(directionalLight);

    // Añadir suelo (plano invisible)
    const groundGeometry = new THREE.PlaneGeometry(200, 200);
    const groundMaterial = new THREE.MeshStandardMaterial({
        color: 0x1a1a2e,
        side: THREE.DoubleSide
    });
    const groundMesh = new THREE.Mesh(groundGeometry, groundMaterial);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.receiveShadow = true;
    threeScene.add(groundMesh);

    // Crear mundo físico para el suelo
    const groundBody = new CANNON.Body({
        mass: 0,
        shape: new CANNON.Plane(),
        position: new CANNON.Vec3(0, 0, 0)
    });
    physicsWorld.addBody(groundBody);

    // Configurar controles de orbitación (para rotar la cámara)
    controls = new THREE.OrbitControls(threeCamera, threeRenderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 30;
    controls.maxDistance = 200;
    controls.maxPolarAngle = Math.PI / 2;

    // Manejar eventos de redimensionamiento
    window.addEventListener('resize', onWindowResize);

    // Iniciar animación
    animate();
}

// Crear un objeto físico con propiedades personalizables
function createPhysicsObject(options = {}) {
    const defaults = {
        mass: 1,
        width: 10,
        height: 10,
        depth: 10,
        color: 0x00d4ff,
        position: { x: 0, y: 0, z: 0 },
        velocity: { x: 0, y: 0, z: 0 },
        angularVelocity: { x: 0, y: 0, z: 0 },
        userData: {}
    };

    const config = { ...defaults, ...options };

    // Crear cuerpo físico en Cannon
    const shape = new CANNON.Box(new CANNON.Vec3(
        config.width / 2,
        config.height / 2,
        config.depth / 2
    ));

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

    // Crear malla en Three.js
    const geometry = new THREE.BoxGeometry(
        config.width,
        config.height,
        config.depth
    );

    const material = new THREE.MeshStandardMaterial({
        color: config.color,
        metalness: 0.3,
        roughness: 0.7,
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = {
        physicsBody: body,
        originalPosition: config.position,
        originalColor: config.color,
        originalSize: { width: config.width, height: config.height, depth: config.depth }
    };

    // Añadir cuerpo físico al mundo
    physicsWorld.addBody(body);

    // Añadir malla a la escena
    threeScene.add(mesh);

    return {
        mesh: mesh,
        body: body,
        update: function() {
            // Sincronizar posición entre Three.js y Cannon
            if (body.position) {
                mesh.position.copy(body.position);
            }
            if (body.quaternion) {
                mesh.quaternion.copy(body.quaternion);
            }
        }
    };
}

// Crear un cubo de prueba (para verificar que el sistema funciona)
function createTestCube() {
    return createPhysicsObject({
        mass: 2,
        width: 8,
        height: 8,
        depth: 8,
        color: 0xff00aa,
        position: { x: 0, y: 0, z: 0 },
        userData: {
            type: 'test_cube',
            description: 'Cubo de prueba para verificar física 3D'
        }
    });
}

// Manejar eventos de arrastre con física realista
function setupDragControls() {
    const dragControls = new THREE.DragControls(
        [threeScene.children.filter(child => child.userData.physicsBody)],
        threeCamera,
        threeRenderer.domElement
    );

    dragControls.addEventListener('dragstart', function(event) {
        const object = event.object;
        dragObject = object;
        dragOffset = {
            x: object.position.x - mouse.x,
            y: object.position.y - mouse.y
        };

        // Aplicar fuerza de arrastre (efecto de resorte)
        const body = object.userData.physicsBody;
        body.velocity.set(0, 0, 0);
        body.angularVelocity.set(0, 0, 0);

        // Guardar posición original para efecto de resorte
        object.userData.originalPosition = {
            x: body.position.x,
            y: body.position.y,
            z: body.position.z
        };
    });

    dragControls.addEventListener('drag', function(event) {
        const object = event.object;
        const body = object.userData.physicsBody;

        // Posición del cursor en coordenadas 3D
        const vector = new THREE.Vector3(
            (mouse.x / windowHalf.width) * 100 - 50,
            -(mouse.y / windowHalf.height) * 100 + 50,
            0
        );

        // Aplicar fuerza de resorte (efecto de seguimiento con inercia)
        const springForce = PHYSICS_CONFIG.springConstant;
        const targetX = vector.x - dragOffset.x;
        const targetY = vector.y - dragOffset.y;

        // Calcular fuerza hacia la posición del cursor
        const forceX = (targetX - body.position.x) * springForce;
        const forceY = (targetY - body.position.y) * springForce;

        // Aplicar fuerza al cuerpo físico
        body.force.set(forceX, forceY, 0);
    });

    dragControls.addEventListener('dragend', function(event) {
        const object = event.object;
        const body = object.userData.physicsBody;

        // Liberar el objeto (quitar fuerza de arrastre)
        body.force.set(0, 0, 0);

        // Aplicar un pequeño impulso para efecto de inercia
        body.velocity.set(
            (Math.random() - 0.5) * 2,
            (Math.random() - 0.5) * 2,
            0
        );

        dragObject = null;
    });

    // Manejar eventos de mouse
    document.addEventListener('mousemove', (event) => {
        mouse.x = (event.clientX - windowHalf.width) * 2;
        mouse.y = (event.clientY - windowHalf.height) * 2;
    });

    document.addEventListener('mousedown', (event) => {
        if (event.button === 0) { // Botón izquierdo del mouse
            // Verificar si se hizo clic en un objeto físico
            const raycaster = new THREE.Raycaster();
            const mouseVector = new THREE.Vector2();
            mouseVector.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouseVector.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouseVector, threeCamera);
            const intersects = raycaster.intersectObjects(
                threeScene.children.filter(child => child.userData.physicsBody)
            );

            if (intersects.length > 0) {
                const object = intersects[0].object;
                const body = object.userData.physicsBody;

                // Aplicar efecto de "agarre" (fuerza hacia el cursor)
                const vector = new THREE.Vector3(
                    (event.clientX / window.innerWidth) * 200 - 100,
                    -(event.clientY / window.innerHeight) * 200 + 100,
                    0
                );

                body.velocity.set(
                    (vector.x - body.position.x) * 0.5,
                    (vector.y - body.position.y) * 0.5,
                    0
                );
            }
        }
    });
}

// Animación principal
function animate() {
    requestAnimationFrame(animate);

    // Actualizar física
    const timeStep = 1/60;
    physicsWorld.step(timeStep);

    // Actualizar objetos en la escena
    threeScene.children.forEach(object => {
        if (object.userData.physicsBody) {
            object.update();
        }
    });

    // Actualizar controles
    controls.update();

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

// Inicializar el sistema de física
function initPhysicsUI() {
    // Cargar librerías necesarias
    if (!window.THREE) {
        console.error("Three.js no está cargado. Asegúrate de incluir la librería.");
        return;
    }

    if (!window.CANNON) {
        console.error("Cannon-es no está cargado. Asegúrate de incluir la librería.");
        return;
    }

    // Inicializar el mundo físico
    initPhysicsWorld();

    // Crear cubo de prueba
    const testCube = createTestCube();

    // Configurar controles de arrastre
    setupDragControls();

    console.log("🚀 PHYSICS UI ENGINE INICIALIZADO");
    console.log("   - Mundo físico con Cannon-es");
    console.log("   - Escena 3D con Three.js");
    console.log("   - Controles de arrastre con física realista");
    console.log("   - Cubo de prueba creado (masa=2, color=morado)");
}

// Exportar funciones para uso externo
window.PhysicsUI = {
    init: initPhysicsUI,
    createObject: createPhysicsObject,
    config: PHYSICS_CONFIG
};

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si Three.js y Cannon-es están disponibles
    if (window.THREE && window.CANNON) {
        initPhysicsUI();
    } else {
        console.warn("Esperando carga de Three.js y Cannon-es...");
        const checkInterval = setInterval(() => {
            if (window.THREE && window.CANNON) {
                clearInterval(checkInterval);
                initPhysicsUI();
            }
        }, 100);
    }
});
