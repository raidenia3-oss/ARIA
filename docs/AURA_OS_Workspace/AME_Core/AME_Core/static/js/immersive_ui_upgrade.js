/*
Hyper Esthetic Upgrade para AURA Tactical Dashboard.
Incluye animaciones suaves, feedback visual, optimización de rendimiento y control de gestos.
*/

// Configuración global
const immersiveUI = {
    isGestureEnabled: true,
    isHighPerformanceMode: true,
    particleSystems: [],
    animationFrames: [],

    // Inicializar el módulo de UI inmersiva
    init: function() {
        this.setupGestureToggleButton();
        this.setupPerformanceOptimization();
        this.setupEventListeners();
    },

    // Configurar botón para activar/desactivar gestos
    setupGestureToggleButton: function() {
        const toggleButton = document.createElement('button');
        toggleButton.id = 'gesture-toggle-button';
        toggleButton.className = 'gesture-toggle-button';
        toggleButton.innerHTML = `
            <span class="gesture-icon">${this.isGestureEnabled ? '👋' : '🚫'}</span>
            <span class="gesture-label">${this.isGestureEnabled ? 'Gestos ACTIVADOS' : 'Gestos DESACTIVADOS'}</span>
        `;
        toggleButton.style.position = 'fixed';
        toggleButton.style.bottom = '20px';
        toggleButton.style.right = '20px';
        toggleButton.style.zIndex = '9999';
        toggleButton.style.backgroundColor = '#00ff00';
        toggleButton.style.color = '#000000';
        toggleButton.style.border = 'none';
        toggleButton.style.borderRadius = '50%';
        toggleButton.style.width = '120px';
        toggleButton.style.height = '40px';
        toggleButton.style.cursor = 'pointer';
        toggleButton.style.fontSize = '12px';
        toggleButton.style.boxShadow = '0 0 10px rgba(0, 255, 0, 0.5)';
        toggleButton.style.transition = 'all 0.3s ease';

        document.body.appendChild(toggleButton);

        toggleButton.addEventListener('click', () => {
            this.toggleGestureMode();
        });
    },

    // Alternar modo de gestos
    toggleGestureMode: function() {
        this.isGestureEnabled = !this.isGestureEnabled;
        const button = document.getElementById('gesture-toggle-button');
        button.innerHTML = `
            <span class="gesture-icon">${this.isGestureEnabled ? '👋' : '🚫'}</span>
            <span class="gesture-label">${this.isGestureEnabled ? 'Gestos ACTIVADOS' : 'Gestos DESACTIVADOS'}</span>
        `;

        // Cambiar color según el estado
        button.style.backgroundColor = this.isGestureEnabled ? '#00ff00' : '#ff0000';

        // Notificar al gestor de gestos
        if (typeof gestureManager !== 'undefined') {
            gestureManager.isConnected = this.isGestureEnabled;
        }

        // Efecto de sonido o vibración (si está disponible)
        if (this.isGestureEnabled) {
            this.playSound('gesture_enabled');
        } else {
            this.playSound('gesture_disabled');
        }
    },

    // Configurar optimización de rendimiento
    setupPerformanceOptimization: function() {
        // Detectar si el sistema está inactivo
        let lastActivityTime = Date.now();

        // Actualizar el rendimiento según la actividad
        setInterval(() => {
            const currentTime = Date.now();
            const inactivityTime = (currentTime - lastActivityTime) / 1000; // en segundos

            if (inactivityTime > 30 && this.isHighPerformanceMode) {
                this.reducePerformance();
            } else if (inactivityTime <= 10) {
                this.restorePerformance();
            }
        }, 5000);

        // Detectar actividad del usuario
        document.addEventListener('mousemove', () => {
            lastActivityTime = Date.now();
        });

        document.addEventListener('keydown', () => {
            lastActivityTime = Date.now();
        });

        // Detectar gestos como actividad
        if (typeof gestureManager !== 'undefined') {
            gestureManager.socket.on('gesture_detected', () => {
                lastActivityTime = Date.now();
            });
        }
    },

    // Reducir rendimiento para ahorrar recursos
    reducePerformance: function() {
        this.isHighPerformanceMode = false;
        console.log('🔄 Modo de bajo rendimiento activado (30fps)');

        // Reducir FPS en Three.js si está disponible
        if (typeof tacticalDashboard !== 'undefined' && tacticalDashboard.threatRadar) {
            tacticalDashboard.threatRadar.reduceFPS();
        }

        // Notificar al usuario
        this.showNotification('Modo de bajo rendimiento activado para ahorrar recursos.');
    },

    // Restaurar rendimiento completo
    restorePerformance: function() {
        this.isHighPerformanceMode = true;
        console.log('⚡ Modo de alto rendimiento restaurado');

        // Restaurar FPS en Three.js si está disponible
        if (typeof tacticalDashboard !== 'undefined' && tacticalDashboard.threatRadar) {
            tacticalDashboard.threatRadar.restoreFPS();
        }

        // Notificar al usuario
        this.showNotification('Modo de alto rendimiento restaurado.');
    },

    // Mostrar notificación al usuario
    showNotification: function(message) {
        if (!this.notificationElement) {
            this.notificationElement = document.createElement('div');
            this.notificationElement.className = 'immersive-notification';
            this.notificationElement.style.position = 'fixed';
            this.notificationElement.style.top = '20px';
            this.notificationElement.style.right = '20px';
            this.notificationElement.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
            this.notificationElement.style.color = '#00ff00';
            this.notificationElement.style.padding = '10px 15px';
            this.notificationElement.style.borderRadius = '5px';
            this.notificationElement.style.zIndex = '9998';
            this.notificationElement.style.boxShadow = '0 0 10px rgba(0, 255, 0, 0.3)';
            this.notificationElement.style.display = 'none';
            document.body.appendChild(this.notificationElement);
        }

        this.notificationElement.textContent = message;
        this.notificationElement.style.display = 'block';

        setTimeout(() => {
            this.notificationElement.style.display = 'none';
        }, 3000);
    },

    // Configurar eventos para animaciones y feedback
    setupEventListeners: function() {
        // Añadir animaciones CSS a los elementos del dashboard
        this.addCSSAnimations();

        // Configurar feedback visual para el Action Queue
        if (typeof actionQueueManager !== 'undefined') {
            actionQueueManager.socket.on('action_queue_updated', (queue) => {
                this.triggerVisualFeedback();
            });
        }
    },

    // Añadir animaciones CSS a los elementos del dashboard
    addCSSAnimations: function() {
        // Animación para paneles
        const panels = document.querySelectorAll('.panel, .card, .action-item');
        panels.forEach(panel => {
            panel.style.transition = 'all 0.3s ease';
            panel.style.opacity = '0';
            setTimeout(() => {
                panel.style.opacity = '1';
            }, 10);
        });

        // Animación para botones
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.style.transition = 'all 0.2s ease';
            button.addEventListener('mouseenter', () => {
                button.style.transform = 'scale(1.05)';
            });
            button.addEventListener('mouseleave', () => {
                button.style.transform = 'scale(1)';
            });
        });

        // Animación para el cursor de mano
        const handCursor = document.querySelector('.hand-cursor');
        if (handCursor) {
            handCursor.style.transition = 'all 0.1s ease';
        }
    },

    // Disparar feedback visual (partículas 3D)
    triggerVisualFeedback: function() {
        if (typeof tacticalDashboard !== 'undefined' && tacticalDashboard.threatRadar) {
            // Crear efecto de partículas
            this.createParticleEffect();
        }
    },

    // Crear efecto de partículas 3D
    createParticleEffect: function() {
        if (typeof tacticalDashboard !== 'undefined' && tacticalDashboard.threatRadar.canvas) {
            const canvas = tacticalDashboard.threatRadar.canvas;
            const ctx = tacticalDashboard.threatRadar.ctx;

            // Crear partículas
            const particles = [];
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const particleCount = 20;

            for (let i = 0; i < particleCount; i++) {
                const angle = Math.random() * Math.PI * 2;
                const distance = Math.random() * 50 + 20;
                const velocity = Math.random() * 2 + 1;
                const size = Math.random() * 3 + 1;
                const color = `hsl(${Math.random() * 60 + 180}, 100%, 70%)`;

                particles.push({
                    x: centerX + Math.cos(angle) * distance,
                    y: centerY + Math.sin(angle) * distance,
                    vx: Math.cos(angle) * velocity,
                    vy: Math.sin(angle) * velocity,
                    size: size,
                    color: color,
                    life: 100
                });
            }

            // Dibujar partículas
            const drawParticles = () => {
                ctx.save();
                ctx.globalAlpha = 0.8;

                particles.forEach(particle => {
                    ctx.beginPath();
                    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                    ctx.fillStyle = particle.color;
                    ctx.fill();

                    // Actualizar posición
                    particle.x += particle.vx;
                    particle.y += particle.vy;
                    particle.life--;

                    // Reducir velocidad y tamaño con el tiempo
                    particle.vx *= 0.99;
                    particle.vy *= 0.99;
                    particle.size *= 0.98;
                });

                // Eliminar partículas muertas
                for (let i = particles.length - 1; i >= 0; i--) {
                    if (particles[i].life <= 0) {
                        particles.splice(i, 1);
                    }
                }

                ctx.restore();

                if (particles.length > 0) {
                    requestAnimationFrame(drawParticles);
                }
            };

            drawParticles();
        }
    },

    // Reproducir sonidos simples (simulados)
    playSound: function(soundType) {
        const sounds = {
            'gesture_enabled': '🎵 Gestos activados',
            'gesture_disabled': '🎵 Gestos desactivados',
            'action_feedback': '🎵 Acción completada'
        };

        console.log(sounds[soundType]);
        // En un entorno real, podrías usar la API Web Audio para reproducir sonidos
    }
};

// Inicializar el módulo de UI inmersiva cuando la página esté cargada
document.addEventListener('DOMContentLoaded', function() {
    immersiveUI.init();
});
