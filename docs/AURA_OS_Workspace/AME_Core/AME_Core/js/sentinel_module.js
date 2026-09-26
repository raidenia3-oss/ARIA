/**
 * Módulo de Vigilancia Acústica (Centinela) para AME.
 * Monitorea el nivel de decibelios en tiempo real y graba alertas cuando se supera un umbral.
 */

// Configuración del módulo
const SENTINEL_API_URL = 'http://localhost:5000/api/alerts/audio';
const MASTER_API_KEY = 'AURA_MASTER_KEY_2026';
const DEFAULT_THRESHOLD = 60; // Umbral en dB (conversación normal)
const RECORD_DURATION = 10; // Duración de grabación en segundos
const AUDIO_CHUNK_SIZE = 1024; // Tamaño de chunk para procesamiento

// Variables globales para el estado del centinela
let sentinelActive = false;
let audioContext = null;
let analyser = null;
let microphone = null;
let audioRecorder = null;
let animationId = null;
let currentThreshold = DEFAULT_THRESHOLD;
let audioBuffer = [];
let isRecording = false;

// Función para inicializar el contexto de audio
function initAudioContext() {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;

            // Solicitar acceso al micrófono
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    microphone = audioContext.createMediaStreamSource(stream);
                    microphone.connect(analyser);
                    console.log('Micrófono activado correctamente');
                })
                .catch(error => {
                    console.error('Error al acceder al micrófono:', error);
                });
        }
    } catch (error) {
        console.error('Error al inicializar AudioContext:', error);
    }
}

// Función para calcular el nivel de decibelios
function getDecibelLevel() {
    if (!analyser) return 0;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    analyser.getByteFrequencyData(dataArray);

    // Calcular el nivel promedio
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
    }
    const average = sum / bufferLength;

    // Convertir a decibelios (aproximación)
    // Fórmula simplificada: dB ≈ 20 * log10(amplitud)
    // Para simplificar, usamos una escala lineal basada en el promedio
    const linearValue = average / 128.0; // Normalizar a 0-1
    const dB = 20 * Math.log10(Math.max(0.0001, linearValue)); // Evitar log(0)

    return Math.max(-80, Math.min(0, dB)); // Limitar el rango
}

// Función para actualizar la visualización del nivel acústico
function updateAudioLevelDisplay(level) {
    const audioLevelFill = document.getElementById('audio-level-fill');
    const audioLevelValue = document.getElementById('audio-level-value');

    if (audioLevelFill && audioLevelValue) {
        // Normalizar el nivel a un rango de 0-100 para la barra
        const normalizedLevel = Math.min(100, Math.max(0, (level + 80) / 1.6)); // -80dB a 0dB → 0-100
        audioLevelFill.style.width = `${normalizedLevel}%`;
        audioLevelValue.textContent = `${Math.round(level)} dB`;

        // Cambiar color según el nivel
        if (level > currentThreshold) {
            audioLevelFill.style.backgroundColor = 'var(--accent-color)';
        } else {
            audioLevelFill.style.backgroundColor = 'var(--accent-secondary)';
        }
    }
}

// Función para iniciar el monitoreo del centinela
function startSentinelMode(threshold = DEFAULT_THRESHOLD) {
    currentThreshold = threshold;
    sentinelActive = true;
    isRecording = false;

    // Inicializar contexto de audio si no está inicializado
    if (!audioContext) {
        initAudioContext();
    }

    // Mostrar estado en la UI
    const sentinelStatusDiv = document.getElementById('sentinel-status');
    if (sentinelStatusDiv) {
        sentinelStatusDiv.textContent = `Estado: Activo (Umbral: ${threshold} dB)`;
    }

    // Iniciar el bucle de animación para monitorear el audio
    function monitorAudio() {
        if (!sentinelActive) return;

        const level = getDecibelLevel();
        updateAudioLevelDisplay(level);

        // Verificar si se superó el umbral
        if (level > currentThreshold && !isRecording) {
            console.log(`🚨 Alerta de ruido detectada: ${level} dB (umbral: ${currentThreshold} dB)`);
            startRecording();
        }

        animationId = requestAnimationFrame(monitorAudio);
    }

    monitorAudio();
}

// Función para iniciar la grabación de audio
async function startRecording() {
    if (!microphone || isRecording) return;

    isRecording = true;
    audioBuffer = [];

    console.log('🎤 Iniciando grabación de alerta...');

    try {
        // Usar MediaRecorder para grabar audio
        const stream = microphone.mediaStream;
        audioRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/wav',
            audioBitsPerSecond: 128000
        });

        audioRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioBuffer.push(event.data);
            }
        };

        audioRecorder.onstop = async () => {
            try {
                // Combinar los chunks de audio
                const blob = new Blob(audioBuffer, { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(blob);

                // Enviar el audio a AURA
                const formData = new FormData();
                formData.append('audio', blob, `ALERTA_${new Date().toISOString().replace(/[:.]/g, '-')}.wav`);
                formData.append('threshold', currentThreshold.toString());
                formData.append('level', getDecibelLevel().toString());

                const response = await fetch(SENTINEL_API_URL, {
                    method: 'POST',
                    headers: { 'X-API-KEY': MASTER_API_KEY },
                    body: formData
                });

                if (response.ok) {
                    const result = await response.json();
                    console.log('📤 Audio enviado a AURA:', result);
                } else {
                    console.error('❌ Error al enviar audio a AURA');
                }

                // Liberar recursos
                URL.revokeObjectURL(audioUrl);
            } catch (error) {
                console.error('Error al procesar grabación:', error);
            } finally {
                isRecording = false;
            }
        };

        // Configurar la duración de la grabación
        audioRecorder.start(RECORD_DURATION * 1000); // Duración en milisegundos

        // Detener después de la duración especificada
        setTimeout(() => {
            if (audioRecorder && audioRecorder.state !== 'inactive') {
                audioRecorder.stop();
            }
        }, RECORD_DURATION * 1000);

    } catch (error) {
        console.error('Error al iniciar grabación:', error);
        isRecording = false;
    }
}

// Función para detener el modo centinela
function stopSentinelMode() {
    sentinelActive = false;
    isRecording = false;

    // Detener cualquier grabación en curso
    if (audioRecorder && audioRecorder.state !== 'inactive') {
        audioRecorder.stop();
    }

    // Limpiar el contexto de audio
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }

    // Mostrar estado en la UI
    const sentinelStatusDiv = document.getElementById('sentinel-status');
    if (sentinelStatusDiv) {
        sentinelStatusDiv.textContent = 'Estado: Inactivo';
    }

    // Limpiar la visualización del nivel acústico
    const audioLevelFill = document.getElementById('audio-level-fill');
    const audioLevelValue = document.getElementById('audio-level-value');
    if (audioLevelFill && audioLevelValue) {
        audioLevelFill.style.width = '0%';
        audioLevelValue.textContent = '0 dB';
    }

    console.log('🛑 Modo Centinela detenido');
}

// Función para manejar el cambio de umbral
function handleThresholdChange(threshold) {
    currentThreshold = parseInt(threshold) || DEFAULT_THRESHOLD;
    console.log(`🎛️ Umbral ajustado a: ${currentThreshold} dB`);

    // Mostrar el nuevo umbral en la UI
    const thresholdInput = document.getElementById('sentinel-threshold');
    if (thresholdInput) {
        thresholdInput.value = currentThreshold;
    }
}

// Inicialización del módulo
function initSentinelModule() {
    // Verificar si los elementos del centinela ya existen
    const startSentinelBtn = document.getElementById('start-sentinel-mode');
    const stopSentinelBtn = document.getElementById('stop-sentinel-mode');
    const thresholdInput = document.getElementById('sentinel-threshold');

    if (startSentinelBtn && stopSentinelBtn && thresholdInput) {
        // Event listeners para los botones
        startSentinelBtn.addEventListener('click', () => {
            const threshold = parseInt(thresholdInput.value) || DEFAULT_THRESHOLD;
            startSentinelMode(threshold);
        });

        stopSentinelBtn.addEventListener('click', stopSentinelMode);

        // Event listener para cambiar el umbral
        thresholdInput.addEventListener('change', (e) => {
            const threshold = e.target.value;
            handleThresholdChange(threshold);
        });

        // Inicializar el contexto de audio al cargar la página
        initAudioContext();
    }
}

// Exportar funciones para que puedan ser usadas desde otros módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        startSentinelMode,
        stopSentinelMode,
        handleThresholdChange,
        initSentinelModule
    };
}

// Inicializar el módulo cuando la página esté lista
document.addEventListener('DOMContentLoaded', initSentinelModule);