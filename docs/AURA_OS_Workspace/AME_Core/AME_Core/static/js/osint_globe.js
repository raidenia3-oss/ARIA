/*
Módulo para el globo terráqueo OSINT interactivo.
Reemplaza la escena actual con un modelo 3D de la Tierra usando THREE.SphereGeometry.
*/

// Importar dependencias de Three.js
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Función para convertir coordenadas geográficas a un vector 3D en la esfera
function latLongToVector3(lat, lon, radius) {
    // Convertir latitud y longitud a radianes
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);

    // Calcular las coordenadas 3D en la esfera
    const x = -(radius * Math.sin(phi) * Math.cos(theta));
    const y = radius * Math.cos(phi);
    const z = radius * Math.sin(phi) * Math.sin(theta);

    return new THREE.Vector3(x, y, z);
}

// Configuración global del globo terráqueo
const globeConfig = {
    scene: null,
    camera: null,
    renderer: null,
    globe: null,
    controls: null,
    anomalies: [],
    newsFeed: [],
    init: function() {
        // Crear la escena
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x000000);

        // Crear la cámara
        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.z = 5;

        // Crear el renderizador
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(window.innerWidth / 2, window.innerHeight * 0.7);
        this.renderer.setPixelRatio(window.devicePixelRatio);

        // Añadir el renderizador al DOM
        const globeContainer = document.getElementById('osint-globe-container');
        if (globeContainer) {
            globeContainer.appendChild(this.renderer.domElement);
        } else {
            console.error("❌ No se encontró el contenedor 'osint-globe-container' en el DOM.");
            return;
        }

        // Crear el globo terráqueo con estilo "Wireframe"
        this.createGlobe();

        // Añadir controles de órbita para rotar con el ratón
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.screenSpacePanning = false;
        this.controls.minDistance = 3;
        this.controls.maxDistance = 10;

        // Añadir luces
        this.addLights();

        // Iniciar el bucle de renderizado
        this.animate();
    },

    createGlobe: function() {
        // Crear la geometría de la esfera
        const globeGeometry = new THREE.SphereGeometry(1, 64, 64);

        // Material con estilo "Wireframe" en cian oscuro
        const globeMaterial = new THREE.MeshBasicMaterial({
            color: 0x00ffff, // Cian oscuro
            wireframe: true,
            transparent: true,
            opacity: 0.8
        });

        // Crear el globo
        this.globe = new THREE.Mesh(globeGeometry, globeMaterial);
        this.scene.add(this.globe);

        // Añadir líneas de longitud y latitud (opcional)
        this.addGridLines();
    },

    addGridLines: function() {
        // Líneas de latitud (paralelos)
        for (let lat = -80; lat <= 80; lat += 10) {
            const latitude = lat * (Math.PI / 180);
            const radius = Math.cos(latitude);
            const points = [];
            for (let lon = 0; lon <= 360; lon += 10) {
                const longitude = lon * (Math.PI / 180);
                const x = radius * Math.cos(longitude);
                const y = Math.sin(latitude);
                const z = radius * Math.sin(longitude);
                points.push(new THREE.Vector3(x, y, z));
            }
            const curve = new THREE.CatmullRomCurve3(points);
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const material = new THREE.LineBasicMaterial({ color: 0x00aaaa, transparent: true, opacity: 0.5 });
            const line = new THREE.Line(geometry, material);
            this.scene.add(line);
        }

        // Líneas de longitud (meridianos)
        for (let lon = 0; lon <= 360; lon += 10) {
            const longitude = lon * (Math.PI / 180);
            const points = [];
            for (let lat = -80; lat <= 80; lat += 10) {
                const latitude = lat * (Math.PI / 180);
                const radius = Math.cos(latitude);
                const x = radius * Math.cos(longitude);
                const y = Math.sin(latitude);
                const z = radius * Math.sin(longitude);
                points.push(new THREE.Vector3(x, y, z));
            }
            const curve = new THREE.CatmullRomCurve3(points);
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const material = new THREE.LineBasicMaterial({ color: 0x00aaaa, transparent: true, opacity: 0.5 });
            const line = new THREE.Line(geometry, material);
            this.scene.add(line);
        }
    },

    addLights: function() {
        // Luz ambiental
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);

        // Luz direccional (simular luz solar)
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(1, 1, 1);
        this.scene.add(directionalLight);
    },

    addAnomaly: function(lat, lon, color = 0xff0000, size = 0.05) {
        // Convertir coordenadas geográficas a vector 3D
        const vector = latLongToVector3(lat, lon, 1.05); // 5% más grande que el globo

        // Crear una esfera para la anomalía
        const geometry = new THREE.SphereGeometry(size, 16, 16);
        const material = new THREE.MeshBasicMaterial({ color: color });
        const anomaly = new THREE.Mesh(geometry, material);

        // Añadir la anomalía a la escena
        anomaly.position.copy(vector);
        this.scene.add(anomaly);

        // Guardar la referencia
        this.anomalies.push(anomaly);
    },

    addNewsMarker: function(lat, lon, text) {
        // Convertir coordenadas geográficas a vector 3D
        const vector = latLongToVector3(lat, lon, 1.1); // 10% más grande que el globo

        // Crear un texto 3D (simplificado)
        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 64;
        const context = canvas.getContext('2d');
        context.fillStyle = 'rgba(255, 255, 255, 0.8)';
        context.font = '12px Courier New';
        context.fillText(text, 10, 30);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture });
        const sprite = new THREE.Sprite(material);
        sprite.position.copy(vector);
        sprite.scale.set(0.2, 0.1, 1);
        this.scene.add(sprite);

        // Guardar la referencia
        this.newsFeed.push({ sprite: sprite, text: text });
    },

    updateAnomalies: function(data) {
        // Limpiar anomalías anteriores
        this.anomalies.forEach(anomaly => {
            this.scene.remove(anomaly);
        });
        this.anomalies = [];

        // Limpiar marcadores de noticias anteriores
        this.newsFeed.forEach(marker => {
            this.scene.remove(marker.sprite);
        });
        this.newsFeed = [];

        // Añadir nuevas anomalías (aviones, barcos, etc.)
        if (data.aircraft) {
            data.aircraft.forEach(aircraft => {
                this.addAnomaly(aircraft.lat, aircraft.lon, 0xff0000, 0.05);
            });
        }

        // Añadir marcadores de noticias geopolíticas
        if (data.news) {
            data.news.forEach(news => {
                this.addNewsMarker(news.lat, news.lon, news.title);
            });
        }
    },

    animate: function() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    },

    resize: function() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth / 2, window.innerHeight * 0.7);
    }
};

// Exportar la configuración global
export { globeConfig, latLongToVector3 };
