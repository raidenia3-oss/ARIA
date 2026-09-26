/*
Módulo para gestionar los gestos holográficos y el globo terráqueo OSINT.
*/

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { globeConfig, latLongToVector3 } from './osint_globe.js';

// Configuración global del holograma
const hologramConfig = {
    scene: null,
    camera: null,
    renderer: null,
    globe: null,
    controls: null,
    anomalies: [],
    newsFeed: [],
    init: function() {
        // Inicializar el globo terráqueo
        globeConfig.init();

        // Configurar eventos de redimensionamiento
        window.addEventListener('resize', () => {
            globeConfig.resize();
        });

        // Cargar datos OSINT simulados (se actualizarán desde el backend)
        this.loadSimulatedData();
    },

    loadSimulatedData: function() {
        // Simular datos OSINT (se reemplazarán con datos reales desde el backend)
        const simulatedData = {
            aircraft: [
                { lat: 40.7128, lon: -74.0060, altitude: 38000, speed: 500 },
                { lat: 51.5074, lon: -0.1278, altitude: 35000, speed: 450 },
                { lat: 34.0522, lon: -118.2437, altitude: 40000, speed: 550 }
            ],
            news: [
                { lat: 37.7749, lon: -122.4194, title: "🚨 Tensión en San Francisco: Protestas cerca del puerto" },
                { lat: 52.5200, lon: 13.4050, title: "🇪🇺 Berlín: Nuevo acuerdo comercial con Asia" },
                { lat: 48.8566, lon: 2.3522, title: "🇫🇷 París: Manifestaciones por reforma laboral" }
            ]
        };

        // Actualizar el globo con los datos simulados
        globeConfig.updateAnomalies(simulatedData);
    },

    updateFromBackend: function(data) {
        // Actualizar el globo con datos reales del backend
        globeConfig.updateAnomalies(data);
    }
};

// Inicializar el holograma cuando el DOM esté cargado
document.addEventListener('DOMContentLoaded', function() {
    hologramConfig.init();
});
