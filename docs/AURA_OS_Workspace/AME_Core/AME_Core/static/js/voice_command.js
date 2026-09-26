/*
 * Mobile Voice UI para AURA - Optimizado para redes móviles
 * Implementa un botón de "Push-to-Talk" con grabación de audio optimizada para bajo consumo de datos
 */

// Configuración global optimizada para redes móviles
const VOICE_COMMAND_CONFIG = {
    serverUrl: 'https://aura-server-01.vercel.app/api/voice-command',
    maxRecordingTime: 30, // Máximo tiempo de grabación en segundos
    minRecordingTime: 1,  // Tiempo mínimo de grabación en segundos
    audioFormat: 'audio/webm;codecs=opus', // Usar códec Opus para mejor compresión
    sampleRate: 16000, // Frecuencia de muestreo baja para ahorrar datos
    bitsPerSecond: 16000, // Bitrate bajo (16kbps) para redes móviles
    channels: 1, // Monoaural para ahorrar datos
    feedbackInterval: 100, // Milisegundos para actualizar el feedback visual
    pulseAnimationDuration: 1000, // Duración de la animación de pulso
    pulseAnimationDelay: 500, // Retraso entre pulsos
    audioVisualizationSamples: 64, // Reducir muestras para visualización (menos consumo)
    audioVisualizationUpdateRate: 100, // Actualizar menos frecuentemente
    mobileOptimization: true, // Modo optimizado para redes móviles
    connectionQuality: 'unknown', // Calidad de conexión detectada
    retryAttempts: 3, // Intentos de reenvío automático
    retryDelay: 2000, // Retraso entre reintentos (ms)
    maxAudioSize: 500000, // Límite de tamaño de audio (500KB) para redes móviles
    compressionQuality: 0.5 // Calidad de compresión (0-1, donde 0.5 es un buen equilibrio)
};

// Estado del componente
let voiceCommandState = {
    isRecording: false,
    recordingStartTime: null,
    recordingTimer: null,
    audioChunks: [],
    mediaRecorder: null,
    audioContext: null,
    analyserNode: null,
    dataArray: null,
    animationFrameId: null,
    lastAudioLevel: 0,
    audioVisualizationCanvas: null,
    audioVisualizationCtx: null,
    audioVisualizationData: [],
    lastVisualizationTime: 0,
    connectionStatus: 'unknown',
    retryCount: 0,
    lastSentTime: null,
    isOffline: false,
    offlineQueue: [],
    networkRetryTimer: null
};

// Elementos del DOM
let voiceCommandElements = {
    button: null,
    pulseIndicator: null,
    recordingIndicator: null,
    audioVisualization: null,
    statusText: null,
    timerDisplay: null,
    connectionStatusIndicator: null,
    offlineModeIndicator: null
};

// Inicializar el componente de voz
function initVoiceCommand() {
    // Crear elementos del botón de voz
    createVoiceCommandButton();

    // Inicializar el contexto de audio para visualización
    initAudioContext();

    // Configurar eventos
    setupEventListeners();

    // Mostrar el botón en el dashboard
    showVoiceCommandButton();

    // Detectar calidad de conexión
    detectConnectionQuality();

    console.log('🎤 Mobile Voice UI inicializado correctamente (modo optimizado para redes móviles)');
}

// Crear el botón de voz táctico
function createVoiceCommandButton() {
    // Contenedor principal
    const container = document.createElement('div');
    container.className = 'voice-command-container';
    container.id = 'voice-command-container';

    // Botón principal
    const button = document.createElement('button');
    button.className = 'voice-command-button';
    button.id = 'voice-command-button';
    button.innerHTML = `
        <i class="voice-command-icon"></i>
        <span class="voice-command-text">Presiona y habla</span>
    `;

    // Indicador de pulso (animación)
    const pulseIndicator = document.createElement('div');
    pulseIndicator.className = 'voice-command-pulse';
    pulseIndicator.id = 'voice-command-pulse';

    // Indicador de grabación
    const recordingIndicator = document.createElement('div');
    recordingIndicator.className = 'voice-command-recording-indicator';
    recordingIndicator.id = 'voice-command-recording-indicator';

    // Visualización de audio
    const audioVisualization = document.createElement('canvas');
    audioVisualization.className = 'voice-command-audio-visualization';
    audioVisualization.id = 'voice-command-audio-visualization';
    audioVisualization.width = 120;
    audioVisualization.height = 30;

    // Texto de estado
    const statusText = document.createElement('div');
    statusText.className = 'voice-command-status-text';
    statusText.id = 'voice-command-status-text';
    statusText.textContent = 'Listo para grabar';

    // Display del temporizador
    const timerDisplay = document.createElement('div');
    timerDisplay.className = 'voice-command-timer-display';
    timerDisplay.id = 'voice-command-timer-display';
    timerDisplay.textContent = '00:00';

    // Indicador de calidad de conexión
    const connectionStatusIndicator = document.createElement('div');
    connectionStatusIndicator.className = 'voice-command-connection-status';
    connectionStatusIndicator.id = 'voice-command-connection-status';

    // Indicador de modo offline
    const offlineModeIndicator = document.createElement('div');
    offlineModeIndicator.className = 'voice-command-offline-indicator';
    offlineModeIndicator.id = 'voice-command-offline-indicator';
    offlineModeIndicator.textContent = 'Modo offline';
    offlineModeIndicator.style.display = 'none';

    // Añadir elementos al contenedor
    container.appendChild(button);
    container.appendChild(pulseIndicator);
    container.appendChild(recordingIndicator);
    container.appendChild(audioVisualization);
    container.appendChild(statusText);
    container.appendChild(timerDisplay);
    container.appendChild(connectionStatusIndicator);
    container.appendChild(offlineModeIndicator);

    // Guardar referencias
    voiceCommandElements = {
        ...voiceCommandElements,
        button,
        pulseIndicator,
        recordingIndicator,
        audioVisualization,
        statusText,
        timerDisplay,
        connectionStatusIndicator,
        offlineModeIndicator
    };

    // Añadir al body (o al dashboard si está disponible)
    document.body.appendChild(container);

    // Inicializar canvas de visualización
    voiceCommandElements.audioVisualizationCanvas = voiceCommandElements.audioVisualization;
    voiceCommandElements.audioVisualizationCtx = voiceCommandElements.audioVisualization.getContext('2d');
}

// Mostrar el botón en el dashboard
function showVoiceCommandButton() {
    // Intentar añadir al dashboard si existe
    const dashboard = document.getElementById('dashboard-container') ||
                     document.getElementById('main-content') ||
                     document.getElementById('app');

    if (dashboard) {
        dashboard.appendChild(voiceCommandElements.button.parentElement);
    } else {
        // Si no hay dashboard, mantenerlo en el body
        document.body.appendChild(voiceCommandElements.button.parentElement);
    }

    // Posicionar el botón en la parte inferior
    voiceCommandElements.button.parentElement.style.position = 'fixed';
    voiceCommandElements.button.parentElement.style.bottom = '20px';
    voiceCommandElements.button.parentElement.style.left = '50%';
    voiceCommandElements.button.parentElement.style.transform = 'translateX(-50%)';
    voiceCommandElements.button.parentElement.style.zIndex = '1000';
    voiceCommandElements.button.parentElement.style.width = '280px';
    voiceCommandElements.button.parentElement.style.textAlign = 'center';
}

// Inicializar el contexto de audio para visualización
function initAudioContext() {
    try {
        voiceCommandState.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        voiceCommandState.analyserNode = voiceCommandState.audioContext.createAnalyser();
        voiceCommandState.analyserNode.fftSize = voiceCommandState.audioVisualizationSamples;

        // Crear buffer para datos de audio
        voiceCommandState.dataArray = new Uint8Array(voiceCommandState.audioVisualizationSamples);

        // Inicializar datos de visualización
        voiceCommandState.audioVisualizationData = new Array(voiceCommandState.audioVisualizationSamples).fill(0);
    } catch (e) {
        console.error('⚠️  No se pudo inicializar el contexto de audio:', e);
        // Continuar sin visualización de audio si no es soportado
    }
}

// Configurar eventos del botón
function setupEventListeners() {
    // Evento de toque (para dispositivos móviles)
    voiceCommandElements.button.addEventListener('touchstart', handleVoiceCommandStart, { passive: false });
    voiceCommandElements.button.addEventListener('touchend', handleVoiceCommandEnd, { passive: false });
    voiceCommandElements.button.addEventListener('touchcancel', handleVoiceCommandCancel);

    // Evento de mouse (para escritorio)
    voiceCommandElements.button.addEventListener('mousedown', handleVoiceCommandStart);
    voiceCommandElements.button.addEventListener('mouseup', handleVoiceCommandEnd);
    voiceCommandElements.button.addEventListener('mouseleave', handleVoiceCommandCancel);

    // Evento de clic (para dispositivos que no soportan touch)
    voiceCommandElements.button.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
    });

    // Evento para detectar cambios en la conexión a red
    window.addEventListener('online', handleNetworkChange);
    window.addEventListener('offline', handleNetworkChange);
}

// Detectar calidad de conexión
function detectConnectionQuality() {
    try {
        // Verificar si estamos en una conexión móvil
        if (navigator.connection) {
            const connection = navigator.connection;
            voiceCommandState.connectionQuality = connection.effectiveType || 'unknown';

            // Actualizar indicador de conexión
            updateConnectionStatusIndicator();

            // Escuchar cambios en la conexión
            connection.addEventListener('change', function() {
                voiceCommandState.connectionQuality = connection.effectiveType || 'unknown';
                updateConnectionStatusIndicator();

                // Si estamos en una conexión móvil, activar optimizaciones
                if (voiceCommandState.connectionQuality === '4g' ||
                    voiceCommandState.connectionQuality === '3g' ||
                    voiceCommandState.connectionQuality === '2g') {
                    enableMobileOptimizations();
                } else {
                    disableMobileOptimizations();
                }
            });
        }

        // Verificar conexión a internet
        checkInternetConnection();

        // Configurar intervalo para verificar periódicamente
        voiceCommandState.connectionCheckInterval = setInterval(checkInternetConnection, 30000);

    } catch (e) {
        console.error('⚠️  Error al detectar calidad de conexión:', e);
        voiceCommandState.connectionQuality = 'unknown';
        updateConnectionStatusIndicator();
    }
}

// Verificar conexión a internet
function checkInternetConnection() {
    try {
        // Usar fetch para verificar conexión
        fetch('https://www.google.com', {
            method: 'HEAD',
            cache: 'no-store',
            mode: 'no-cors',
            redirect: 'follow',
            timeout: 3000
        })
        .then(response => {
            if (response.ok || response.status === 0) {
                voiceCommandState.isOffline = false;
                updateConnectionStatusIndicator();
                clearOfflineQueue();
            } else {
                throw new Error('No conectado a internet');
            }
        })
        .catch(error => {
            voiceCommandState.isOffline = true;
            updateConnectionStatusIndicator();
            console.log('⚠️  Conexión a internet perdida');
        });

    } catch (error) {
        voiceCommandState.isOffline = true;
        updateConnectionStatusIndicator();
        console.log('⚠️  Error al verificar conexión a internet:', error);
    }
}

// Actualizar indicador de conexión
function updateConnectionStatusIndicator() {
    const connectionStatus = voiceCommandState.connectionQuality || 'desconocida';
    let statusText = '';
    let statusColor = '';

    switch(connectionStatus) {
        case '4g':
        case '5g':
            statusText = '📶 4G/5G';
            statusColor = '#4CAF50'; // Verde
            break;
        case '3g':
            statusText = '📶 3G';
            statusColor = '#FF9800'; // Naranja
            break;
        case '2g':
            statusText = '📶 2G';
            statusColor = '#F44336'; // Rojo
            break;
        case 'wifi':
            statusText = '📶 WiFi';
            statusColor = '#2196F3'; // Azul
            break;
        case 'unknown':
        default:
            statusText = '📶 Conexión desconocida';
            statusColor = '#FFC107'; // Amarillo
    }

    // Mostrar indicador de conexión
    voiceCommandElements.connectionStatusIndicator.textContent = statusText;
    voiceCommandElements.connectionStatusIndicator.style.color = statusColor;

    // Mostrar/ocultar según la calidad de conexión
    if (connectionStatus === '2g' || connectionStatus === '3g') {
        voiceCommandElements.connectionStatusIndicator.style.display = 'block';
        enableMobileOptimizations();
    } else {
        voiceCommandElements.connectionStatusIndicator.style.display = 'none';
        disableMobileOptimizations();
    }

    // Mostrar/ocultar indicador de modo offline
    if (voiceCommandState.isOffline) {
        voiceCommandElements.offlineModeIndicator.style.display = 'block';
        showOfflineNotification('Conexión perdida. Los comandos se enviarán cuando regrese la conexión.');
    } else {
        voiceCommandElements.offlineModeIndicator.style.display = 'none';
    }
}

// Activar optimizaciones para redes móviles
function enableMobileOptimizations() {
    if (VOICE_COMMAND_CONFIG.mobileOptimization) {
        console.log('📶 Activando optimizaciones para redes móviles');

        // Reducir aún más la tasa de bits si estamos en 2G/3G
        if (voiceCommandState.connectionQuality === '2g' || voiceCommandState.connectionQuality === '3g') {
            VOICE_COMMAND_CONFIG.bitsPerSecond = 8000; // 8kbps para 2G/3G
            VOICE_COMMAND_CONFIG.sampleRate = 12000; // Frecuencia aún más baja
        } else {
            VOICE_COMMAND_CONFIG.bitsPerSecond = 16000; // 16kbps para 4G/5G
            VOICE_COMMAND_CONFIG.sampleRate = 16000;
        }

        // Mostrar mensaje de optimización
        showSystemNotification('Optimizado para red móvil. Grabando con baja tasa de bits.', 'info');
    }
}

// Desactivar optimizaciones para redes móviles
function disableMobileOptimizations() {
    if (VOICE_COMMAND_CONFIG.mobileOptimization) {
        console.log('📶 Desactivando optimizaciones para redes móviles');

        // Restaurar configuración normal
        VOICE_COMMAND_CONFIG.bitsPerSecond = 16000;
        VOICE_COMMAND_CONFIG.sampleRate = 16000;

        // Mostrar mensaje de optimización
        showSystemNotification('Optimización para red móvil desactivada. Usando configuración normal.', 'info');
    }
}

// Manejar cambios en la conexión a red
function handleNetworkChange() {
    if (window.navigator.onLine) {
        console.log('📶 Conexión a internet restaurada');
        voiceCommandState.isOffline = false;
        updateConnectionStatusIndicator();
        processOfflineQueue();
    } else {
        console.log('📶 Conexión a internet perdida');
        voiceCommandState.isOffline = true;
        updateConnectionStatusIndicator();
    }
}

// Manejar el inicio de la grabación
async function handleVoiceCommandStart(e) {
    e.preventDefault();
    e.stopPropagation();

    if (voiceCommandState.isRecording) return;

    try {
        // Verificar si estamos en modo offline
        if (voiceCommandState.isOffline) {
            showOfflineNotification('Conexión perdida. Presiona el botón para grabar y enviar cuando regrese la conexión.');
            return;
        }

        // Solicitar permiso para usar el micrófono
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                deviceId: { exact: 'default' }, // Usar micrófono por defecto
                sampleRate: VOICE_COMMAND_CONFIG.sampleRate,
                channelCount: VOICE_COMMAND_CONFIG.channels,
                // Configuración adicional para optimización de datos
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        // Inicializar MediaRecorder con configuración optimizada para redes móviles
        const mimeType = VOICE_COMMAND_CONFIG.audioFormat;
        voiceCommandState.mediaRecorder = new MediaRecorder(stream, {
            mimeType: mimeType,
            bitsPerSecond: VOICE_COMMAND_CONFIG.bitsPerSecond
        });

        // Configurar eventos del MediaRecorder
        voiceCommandState.mediaRecorder.ondataavailable = handleDataAvailable;
        voiceCommandState.mediaRecorder.onstop = handleRecordingStop;
        voiceCommandState.mediaRecorder.onerror = handleRecordingError;

        // Iniciar grabación
        voiceCommandState.mediaRecorder.start(100); // Colección cada 100ms

        // Iniciar temporizador
        voiceCommandState.recordingStartTime = Date.now();
        voiceCommandState.recordingTimer = setInterval(updateRecordingTimer, 1000);

        // Iniciar animación de pulso
        startPulseAnimation();

        // Iniciar visualización de audio
        startAudioVisualization(stream);

        // Actualizar estado
        voiceCommandState.isRecording = true;
        voiceCommandState.audioChunks = [];
        voiceCommandState.retryCount = 0;
        voiceCommandState.lastSentTime = null;

        // Actualizar UI
        updateVoiceCommandUI(true);

        console.log('🎤 Grabación iniciada con optimización para redes móviles');

    } catch (error) {
        console.error('❌ Error al iniciar grabación:', error);
        showError('No se pudo acceder al micrófono. Verifica los permisos.');
    }
}

// Manejar la disponibilidad de datos de audio
function handleDataAvailable(e) {
    if (e.data.size > 0) {
        // Limitar el tamaño total del audio para redes móviles
        const currentAudioSize = voiceCommandState.audioChunks.reduce((sum, chunk) => sum + chunk.size, 0);
        if (currentAudioSize + e.data.size <= VOICE_COMMAND_CONFIG.maxAudioSize) {
            voiceCommandState.audioChunks.push(e.data);
        } else {
            console.warn('⚠️  Tamaño máximo de audio alcanzado. Deteniendo grabación.');
            voiceCommandState.mediaRecorder.stop();
        }
    }
}

// Manejar el fin de la grabación
function handleRecordingStop() {
    clearInterval(voiceCommandState.recordingTimer);
    stopPulseAnimation();
    stopAudioVisualization();

    const duration = (Date.now() - voiceCommandState.recordingStartTime) / 1000;

    if (duration >= VOICE_COMMAND_CONFIG.minRecordingTime) {
        // Grabar suficiente tiempo, enviar al servidor
        sendAudioToServer();
    } else {
        // Grabación demasiado corta, descartar
        console.log('🗑️  Grabación demasiado corta, descartada');
        updateVoiceCommandUI(false, 'Grabación demasiado corta');
    }

    // Limpiar estado
    voiceCommandState.isRecording = false;
    voiceCommandState.mediaRecorder = null;
    voiceCommandState.audioChunks = [];
}

// Manejar errores en la grabación
function handleRecordingError(e) {
    console.error('❌ Error en la grabación:', e);
    stopRecording();
    showError('Error al grabar audio. Intenta nuevamente.');
}

// Manejar el fin de la grabación (soltar botón)
function handleVoiceCommandEnd() {
    if (voiceCommandState.isRecording) {
        voiceCommandState.mediaRecorder.stop();
        console.log('🎤 Grabación detenida por el usuario');
    }
}

// Manejar cancelación de grabación
function handleVoiceCommandCancel() {
    if (voiceCommandState.isRecording) {
        voiceCommandState.mediaRecorder.stop();
        console.log('🎤 Grabación cancelada');
    }
}

// Detener la grabación manualmente
function stopRecording() {
    if (voiceCommandState.isRecording) {
        if (voiceCommandState.mediaRecorder && voiceCommandState.mediaRecorder.state !== 'inactive') {
            voiceCommandState.mediaRecorder.stop();
        }
        voiceCommandState.isRecording = false;
    }
}

// Enviar audio al servidor
function sendAudioToServer() {
    if (voiceCommandState.audioChunks.length === 0) return;

    try {
        const audioBlob = new Blob(voiceCommandState.audioChunks, { type: VOICE_COMMAND_CONFIG.audioFormat });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'voice_command.wav');

        // Mostrar estado de envío
        updateVoiceCommandUI(true, 'Enviando al servidor...');

        // Función para intentar enviar el audio
        function attemptSend() {
            fetch(VOICE_COMMAND_CONFIG.serverUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'Accept': 'application/json'
                }
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else if (response.status === 0) {
                    // Conexión fallida
                    throw new Error('Conexión fallida');
                } else {
                    throw new Error('Error al enviar audio al servidor');
                }
            })
            .then(data => {
                console.log('📤 Audio enviado al servidor:', data);
                updateVoiceCommandUI(false, 'Comando enviado');
                showSuccess('Comando de voz procesado con éxito!');

                // REPRODUCCIÓN AUTOMÁTICA DE LA RESPUESTA DE VOZ NATIVA
                if (data.audio_url) {
                    console.log('🔊 Reproduciendo respuesta de voz:', data.audio_url);
                    const audio = new Audio(data.audio_url);
                    audio.play().catch(err => {
                        console.error('Error al reproducir audio de respuesta automáticamente:', err);
                    });
                }

                // Reiniciar estado
                voiceCommandState.retryCount = 0;
                voiceCommandState.lastSentTime = Date.now();
            })
            .catch(error => {
                console.error('❌ Error al enviar audio:', error);

                // Si estamos en modo offline, agregar a la cola
                if (voiceCommandState.isOffline) {
                    addToOfflineQueue(formData);
                    updateVoiceCommandUI(false, 'Comando en cola para envío');
                    showOfflineNotification('Comando grabado en cola. Se enviará cuando regrese la conexión.');
                } else {
                    // Intentar reenviar si hay conexión
                    if (voiceCommandState.retryCount < VOICE_COMMAND_CONFIG.retryAttempts) {
                        voiceCommandState.retryCount++;
                        console.log(`🔄 Reintentando enviar audio (intento ${voiceCommandState.retryCount}/${VOICE_COMMAND_CONFIG.retryAttempts})...`);

                        // Esperar antes de reintentar
                        setTimeout(attemptSend, VOICE_COMMAND_CONFIG.retryDelay);
                    } else {
                        updateVoiceCommandUI(false, 'Error al enviar');
                        showError('Error al enviar comando. Intenta nuevamente.');
                    }
                }
            });
        }

        // Intentar enviar el audio
        attemptSend();

    } catch (error) {
        console.error('❌ Error al preparar audio para envío:', error);
        updateVoiceCommandUI(false, 'Error al enviar');
        showError('Error al preparar el audio para envío.');
    }
}

// Actualizar la interfaz de usuario
function updateVoiceCommandUI(isRecording, statusText = '') {
    if (isRecording) {
        // Estado de grabación
        voiceCommandElements.button.classList.add('recording');
        voiceCommandElements.button.classList.remove('idle');
        voiceCommandElements.recordingIndicator.style.display = 'block';
        voiceCommandElements.statusText.textContent = statusText || 'Grabando...';
        voiceCommandElements.statusText.style.color = '#FF5722';

        // Mostrar temporizador
        voiceCommandElements.timerDisplay.style.display = 'block';
    } else {
        // Estado listo
        voiceCommandElements.button.classList.remove('recording');
        voiceCommandElements.button.classList.add('idle');
        voiceCommandElements.recordingIndicator.style.display = 'none';
        voiceCommandElements.statusText.textContent = statusText || 'Listo para grabar';
        voiceCommandElements.statusText.style.color = '#4CAF50';

        // Ocultar temporizador
        voiceCommandElements.timerDisplay.style.display = 'none';
    }
}

// Actualizar el temporizador de grabación
function updateRecordingTimer() {
    if (!voiceCommandState.isRecording) return;

    const elapsed = Math.floor((Date.now() - voiceCommandState.recordingStartTime) / 1000);
    const remaining = Math.max(0, VOICE_COMMAND_CONFIG.maxRecordingTime - elapsed);

    if (remaining <= 0) {
        // Tiempo máximo alcanzado, detener grabación
        if (voiceCommandState.mediaRecorder && voiceCommandState.mediaRecorder.state !== 'inactive') {
            voiceCommandState.mediaRecorder.stop();
        }
        return;
    }

    // Formatear el tiempo
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    voiceCommandElements.timerDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    // Cambiar color si queda poco tiempo
    if (remaining <= 5) {
        voiceCommandElements.timerDisplay.style.color = '#F44336';
    } else if (remaining <= 10) {
        voiceCommandElements.timerDisplay.style.color = '#FF9800';
    } else {
        voiceCommandElements.timerDisplay.style.color = '#FF5722';
    }
}

// Iniciar animación de pulso
function startPulseAnimation() {
    if (!voiceCommandElements.pulseIndicator) return;

    let pulseCount = 0;
    const pulse = () => {
        if (!voiceCommandState.isRecording) return;

        pulseCount++;
        const scale = 1 + (pulseCount % 2) * 0.3;
        const opacity = 0.7 - (pulseCount % 2) * 0.3;

        voiceCommandElements.pulseIndicator.style.transform = `scale(${scale})`;
        voiceCommandElements.pulseIndicator.style.opacity = opacity;

        if (voiceCommandState.isRecording) {
            voiceCommandElements.animationFrameId = requestAnimationFrame(pulse);
        }
    };

    voiceCommandElements.animationFrameId = requestAnimationFrame(pulse);
}

// Detener animación de pulso
function stopPulseAnimation() {
    if (voiceCommandElements.animationFrameId) {
        cancelAnimationFrame(voiceCommandElements.animationFrameId);
        voiceCommandElements.animationFrameId = null;
    }

    if (voiceCommandElements.pulseIndicator) {
        voiceCommandElements.pulseIndicator.style.transform = 'scale(1)';
        voiceCommandElements.pulseIndicator.style.opacity = '0';
    }
}

// Iniciar visualización de audio
function startAudioVisualization(stream) {
    if (!voiceCommandState.audioContext) return;

    try {
        // Crear source node y conectarlo al analyser
        const source = voiceCommandState.audioContext.createMediaStreamSource(stream);
        source.connect(voiceCommandState.analyserNode);

        // Iniciar actualización de visualización
        const visualize = () => {
            if (!voiceCommandState.isRecording) return;

            // Obtener datos del analisis
            voiceCommandState.analyserNode.getByteFrequencyData(voiceCommandState.dataArray);

            // Actualizar visualización
            updateAudioVisualization();

            // Programar próxima actualización
            voiceCommandElements.animationFrameId = requestAnimationFrame(visualize);
        };

        visualize();
    } catch (e) {
        console.error('⚠️  Error al iniciar visualización de audio:', e);
    }
}

// Detener visualización de audio
function stopAudioVisualization() {
    if (voiceCommandElements.animationFrameId) {
        cancelAnimationFrame(voiceCommandElements.animationFrameId);
        voiceCommandElements.animationFrameId = null;
    }

    // Limpiar canvas
    if (voiceCommandElements.audioVisualizationCtx) {
        voiceCommandElements.audioVisualizationCtx.clearRect(0, 0,
            voiceCommandElements.audioVisualization.width,
            voiceCommandElements.audioVisualization.height);
    }
}

// Actualizar visualización de audio
function updateAudioVisualization() {
    if (!voiceCommandState.audioContext || !voiceCommandState.isRecording) return;

    try {
        const now = Date.now();
        const deltaTime = now - (voiceCommandState.lastVisualizationTime || now);
        voiceCommandState.lastVisualizationTime = now;

        // Calcular nivel de audio promedio
        let sum = 0;
        for (let i = 0; i < voiceCommandState.dataArray.length; i++) {
            sum += voiceCommandState.dataArray[i];
        }
        const audioLevel = sum / voiceCommandState.dataArray.length;

        // Actualizar datos de visualización
        voiceCommandState.audioVisualizationData.unshift(audioLevel);
        if (voiceCommandState.audioVisualizationData.length > voiceCommandState.audioVisualizationSamples) {
            voiceCommandState.audioVisualizationData.pop();
        }

        // Dibujar visualización
        drawAudioVisualization();

    } catch (e) {
        console.error('⚠️  Error al actualizar visualización de audio:', e);
    }
}

// Dibujar visualización de audio
function drawAudioVisualization() {
    if (!voiceCommandElements.audioVisualizationCtx) return;

    const ctx = voiceCommandElements.audioVisualizationCtx;
    const width = voiceCommandElements.audioVisualization.width;
    const height = voiceCommandElements.audioVisualization.height;
    const barWidth = width / voiceCommandState.audioVisualizationData.length;

    // Limpiar canvas
    ctx.clearRect(0, 0, width, height);

    // Dibujar barras de audio
    ctx.fillStyle = '#FF5722';
    ctx.fillRect(0, 0, width, height);

    // Dibujar niveles de audio (simplificado para ahorrar recursos)
    ctx.fillStyle = '#FFC107';
    ctx.beginPath();

    // Solo dibujar cada 4ª barra para ahorrar recursos
    for (let i = 0; i < voiceCommandState.audioVisualizationData.length; i += 4) {
        const barHeight = (voiceCommandState.audioVisualizationData[i] / 255) * height;
        const x = i * barWidth;
        const y = height - barHeight;

        // Dibujar barra redondeada
        ctx.fillRect(x, y, barWidth * 4, barHeight);

        // Dibujar borde
        ctx.strokeStyle = '#FF5722';
        ctx.strokeRect(x, y, barWidth * 4, barHeight);
    }

    ctx.fillStyle = '#FF5722';
    ctx.fillRect(0, 0, width, height);
}

// Mostrar mensaje de éxito
function showSuccess(message) {
    voiceCommandElements.statusText.textContent = message;
    voiceCommandElements.statusText.style.color = '#4CAF50';
    voiceCommandElements.button.classList.add('success');

    setTimeout(() => {
        voiceCommandElements.button.classList.remove('success');
        updateVoiceCommandUI(false, 'Listo para grabar');
    }, 2000);
}

// Mostrar mensaje de error
function showError(message) {
    voiceCommandElements.statusText.textContent = message;
    voiceCommandElements.statusText.style.color = '#F44336';
    voiceCommandElements.button.classList.add('error');

    setTimeout(() => {
        voiceCommandElements.button.classList.remove('error');
        updateVoiceCommandUI(false, 'Listo para grabar');
    }, 3000);
}

// Mostrar notificación del sistema
function showSystemNotification(message, type = 'info') {
    // Implementar notificación del sistema (ya está implementado en dashboard.html)
    if (typeof showSystemNotificationGlobal === 'function') {
        showSystemNotificationGlobal(message, type);
    } else {
        console.log(`🔔 ${type.toUpperCase()}: ${message}`);
    }
}

// Mostrar notificación de modo offline
function showOfflineNotification(message) {
    voiceCommandElements.offlineModeIndicator.textContent = message;
    voiceCommandElements.offlineModeIndicator.style.display = 'block';

    // Mostrar notificación del sistema también
    showSystemNotification(message, 'warning');

    // Ocultar después de 10 segundos
    setTimeout(() => {
        voiceCommandElements.offlineModeIndicator.style.display = 'none';
    }, 10000);
}

// Añadir comando a la cola offline
function addToOfflineQueue(formData) {
    if (!voiceCommandState.offlineQueue) {
        voiceCommandState.offlineQueue = [];
    }

    // Convertir FormData a objeto serializable
    const audioBlob = new Blob(voiceCommandState.audioChunks, { type: VOICE_COMMAND_CONFIG.audioFormat });
    const audioUrl = URL.createObjectURL(audioBlob);

    const queueItem = {
        audioUrl: audioUrl,
        timestamp: Date.now(),
        formData: formData,
        retryCount: 0
    };

    voiceCommandState.offlineQueue.unshift(queueItem);
    console.log(`📥 Comando añadido a cola offline. Tamaño de la cola: ${voiceCommandState.offlineQueue.length}`);
}

// Procesar cola offline cuando regrese la conexión
function processOfflineQueue() {
    if (voiceCommandState.isOffline || !voiceCommandState.offlineQueue || voiceCommandState.offlineQueue.length === 0) {
        return;
    }

    console.log('📡 Conexión restaurada. Procesando cola offline...');

    // Procesar cada elemento de la cola
    voiceCommandState.offlineQueue.forEach((queueItem, index) => {
        // Crear nuevo FormData con el audio
        const formData = new FormData();
        const audioBlob = fetch(queueItem.audioUrl).then(response => response.blob());
        audioBlob.then(blob => {
            formData.append('audio', blob, 'voice_command.webm');

            // Intentar enviar
            sendAudioWithRetry(formData, queueItem.retryCount, index);
        }).catch(error => {
            console.error('❌ Error al procesar audio de la cola:', error);
        });
    });

    // Limpiar la cola después de procesar
    voiceCommandState.offlineQueue = [];
    console.log('📥 Cola offline procesada.');
}

// Enviar audio con reintentos
function sendAudioWithRetry(formData, retryCount, queueIndex) {
    if (retryCount >= VOICE_COMMAND_CONFIG.retryAttempts) {
        console.log('❌ Máximo de reintentos alcanzado para el comando en cola.');
        return;
    }

    fetch(VOICE_COMMAND_CONFIG.serverUrl, {
        method: 'POST',
        body: formData,
        headers: {
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 0) {
            // Conexión fallida
            throw new Error('Conexión fallida');
        } else {
            throw new Error('Error al enviar audio al servidor');
        }
    })
    .then(data => {
        console.log('📤 Comando de la cola enviado al servidor:', data);
        showSystemNotification(`Comando de la cola enviado: ${new Date().toLocaleTimeString()}`, 'success');
    })
    .catch(error => {
        console.error('❌ Error al enviar comando de la cola:', error);

        // Reintentar después de un retraso
        setTimeout(() => {
            sendAudioWithRetry(formData, retryCount + 1, queueIndex);
        }, VOICE_COMMAND_CONFIG.retryDelay);
    });
}

// Limpiar cola offline
function clearOfflineQueue() {
    if (voiceCommandState.offlineQueue) {
        voiceCommandState.offlineQueue.forEach(queueItem => {
            if (queueItem.audioUrl) {
                URL.revokeObjectURL(queueItem.audioUrl);
            }
        });
        voiceCommandState.offlineQueue = [];
    }
}

// Estilos CSS para el componente
function applyVoiceCommandStyles() {
    const style = document.createElement('style');
    style.id = 'voice-command-styles';
    style.textContent = `
        /* Contenedor principal */
        .voice-command-container {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            width: 280px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.8);
            border-radius: 50px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 87, 34, 0.3);
        }

        /* Botón principal */
        .voice-command-button {
            position: relative;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background-color: #FF5722;
            border: none;
            outline: none;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(255, 87, 34, 0.4);
            z-index: 10;
            margin: 0 auto;
        }

        .voice-command-button:hover {
            background-color: #E64A19;
            transform: scale(1.05);
        }

        .voice-command-button:active {
            transform: scale(0.95);
        }

        .voice-command-button.recording {
            background-color: #F44336;
        }

        .voice-command-button.success {
            background-color: #4CAF50;
            animation: pulseSuccess 1.5s;
        }

        .voice-command-button.error {
            background-color: #F44336;
            animation: shakeError 0.5s;
        }

        .voice-command-button.idle {
            background-color: #FF5722;
        }

        /* Icono del micrófono */
        .voice-command-icon {
            font-size: 40px;
            color: white;
            margin-bottom: 5px;
        }

        /* Texto del botón */
        .voice-command-text {
            font-size: 12px;
            color: white;
            font-weight: bold;
            text-align: center;
            line-height: 1.2;
        }

        /* Indicador de pulso */
        .voice-command-pulse {
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background-color: rgba(255, 255, 255, 0.2);
            pointer-events: none;
            transform: scale(0.95);
            opacity: 0;
            transition: transform 0.3s ease, opacity 0.3s ease;
            z-index: 5;
        }

        /* Indicador de grabación */
        .voice-command-recording-indicator {
            position: absolute;
            top: -10px;
            right: -10px;
            width: 20px;
            height: 20px;
            background-color: rgba(0, 255, 0, 0.7);
            border-radius: 50%;
            display: none;
            border: 2px solid white;
            box-shadow: 0 0 5px rgba(0, 255, 0, 0.5);
            z-index: 15;
        }

        /* Visualización de audio */
        .voice-command-audio-visualization {
            width: 120px;
            height: 30px;
            background-color: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            border: 1px solid rgba(255, 87, 34, 0.3);
            margin: 0;
            padding: 0;
        }

        /* Texto de estado */
        .voice-command-status-text {
            font-size: 12px;
            color: #4CAF50;
            margin-top: 5px;
            min-height: 16px;
        }

        /* Display del temporizador */
        .voice-command-timer-display {
            font-size: 14px;
            color: #FF5722;
            font-weight: bold;
            display: none;
            margin-top: 5px;
        }

        /* Indicador de conexión */
        .voice-command-connection-status {
            position: absolute;
            top: -25px;
            right: 0;
            font-size: 10px;
            color: #FFC107;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 2px 6px;
            border-radius: 10px;
            display: none;
            z-index: 20;
        }

        /* Indicador de modo offline */
        .voice-command-offline-indicator {
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 10px;
            color: #F44336;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 2px 8px;
            border-radius: 10px;
            display: none;
            z-index: 20;
        }

        /* Animaciones */
        @keyframes pulseSuccess {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }

        @keyframes shakeError {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-5px); }
            40%, 80% { transform: translateX(5px); }
        }

        /* Responsive */
        @media (max-width: 480px) {
            .voice-command-container {
                width: 240px;
                padding: 10px;
            }

            .voice-command-button {
                width: 100px;
                height: 100px;
            }

            .voice-command-text {
                font-size: 10px;
            }
        }

        /* Estados de conexión */
        .voice-command-connection-status.unknown {
            color: #FFC107;
        }

        .voice-command-connection-status.wifi {
            color: #2196F3;
        }

        .voice-command-connection-status['3g'] {
            color: #FF9800;
        }

        .voice-command-connection-status['2g'] {
            color: #F44336;
        }

        .voice-command-connection-status['4g'] {
            color: #4CAF50;
        }

        .voice-command-connection-status['5g'] {
            color: #00BCD4;
        }
    `;

    document.head.appendChild(style);
}

// Inicializar el componente cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Aplicar estilos
    applyVoiceCommandStyles();

    // Inicializar el componente de voz
    initVoiceCommand();

    console.log('🎤 Mobile Voice UI cargado y listo (modo optimizado para redes móviles)');
});

// Exportar funciones para uso externo
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initVoiceCommand,
        startRecording: handleVoiceCommandStart,
        stopRecording,
        sendAudioToServer,
        detectConnectionQuality,
        checkInternetConnection,
        updateConnectionStatusIndicator
    };
}
