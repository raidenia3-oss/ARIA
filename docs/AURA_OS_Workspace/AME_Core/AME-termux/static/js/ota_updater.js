/**
 * Módulo de Actualización OTA para AME.
 * Detecta actualizaciones disponibles y gestiona la instalación automática.
 */

// Configuración del sistema
const AURA_URL = 'http://localhost:5000';
const LOCAL_STORAGE_KEY = 'ame_version_info';
const UPDATE_CHECK_INTERVAL = 300000; // 5 minutos en milisegundos
const MINIMUM_UPDATE_VERSION = '1.0.0'; // Versión mínima para considerar una actualización

// Variables globales
let updateCheckIntervalId = null;
let isCheckingForUpdate = false;
let isUpdating = false;

// Función para obtener la versión local almacenada
function getLocalVersion() {
    try {
        const storedVersion = localStorage.getItem(LOCAL_STORAGE_KEY);
        if (storedVersion) {
            return JSON.parse(storedVersion);
        }
    } catch (e) {
        console.error('Error al leer versión local:', e);
    }
    return {
        version: '0.0.0',
        build: 0,
        release_date: '1970-01-01'
    };
}

// Función para almacenar la versión local
function setLocalVersion(versionInfo) {
    try {
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(versionInfo));
    } catch (e) {
        console.error('Error al guardar versión local:', e);
    }
}

// Función para comparar versiones
function compareVersions(version1, version2) {
    // Dividir versiones en partes numéricas
    const v1Parts = version1.split('.').map(Number);
    const v2Parts = version2.split('.').map(Number);

    // Asegurar que ambas versiones tengan el mismo número de partes
    while (v1Parts.length < v2Parts.length) v1Parts.push(0);
    while (v2Parts.length < v1Parts.length) v2Parts.push(0);

    // Comparar cada parte
    for (let i = 0; i < v1Parts.length; i++) {
        if (v1Parts[i] > v2Parts[i]) return 1;
        if (v1Parts[i] < v2Parts[i]) return -1;
    }

    // Si son iguales, comparar builds
    if (version1.build > version2.build) return 1;
    if (version1.build < version2.build) return -1;

    return 0;
}

// Función para verificar la versión del servidor
async function checkForUpdates() {
    if (isCheckingForUpdate || isUpdating) return;

    isCheckingForUpdate = true;

    try {
        const response = await fetch(`${AURA_URL}/api/system/version`);
        if (!response.ok) {
            throw new Error(`Error al verificar versión: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        if (data.status !== 'success') {
            throw new Error(`Error en la respuesta del servidor: ${data.message}`);
        }

        const serverVersion = data.version;

        // Obtener versión local
        const localVersion = getLocalVersion();

        // Comparar versiones
        const comparison = compareVersions(serverVersion, localVersion);

        if (comparison > 0) {
            // Hay una actualización disponible
            console.log('🔄 Actualización disponible:', serverVersion.version, 'vs local:', localVersion.version);
            await triggerUpdateProcess(serverVersion);
        } else {
            console.log('🔒 Versión actualizada. No hay actualizaciones disponibles.');
        }

    } catch (error) {
        console.error('Error al verificar actualizaciones:', error);
    } finally {
        isCheckingForUpdate = false;
    }
}

// Función para iniciar el proceso de actualización
async function triggerUpdateProcess(serverVersion) {
    if (isUpdating) return;

    isUpdating = true;

    try {
        // Mostrar modal de actualización
        showUpdateModal(serverVersion);

        // Descargar el APK
        const apkUrl = `${AURA_URL}/descargar-ame`;
        const response = await fetch(apkUrl);

        if (!response.ok) {
            throw new Error(`Error al descargar APK: ${response.status} ${response.statusText}`);
        }

        const blob = await response.blob();
        const apkBlobUrl = URL.createObjectURL(blob);

        // Simular descarga (en un entorno real, mostraría progreso)
        console.log('📥 Descargando APK...');

        // Esperar un momento para simular la descarga
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Instalar el APK (usando Capacitor)
        try {
            // En un entorno real, usaríamos Capacitor para instalar el APK
            // Esto es una simulación para el entorno web
            console.log('🔧 Instalando APK...');

            // Mostrar mensaje de instalación
            updateModal.querySelector('.update-message').textContent = '🔧 Instalando actualización...';

            // Esperar un momento para simular la instalación
            await new Promise(resolve => setTimeout(resolve, 3000));

            // Simular reinicio de la app
            console.log('✅ Actualización instalada. Reiniciando aplicación...');
            updateModal.querySelector('.update-message').textContent = '✅ Actualización instalada. Reiniciando...';

            // En un entorno real, reiniciaríamos la app aquí
            // window.location.reload();

            // Guardar la nueva versión local
            setLocalVersion(serverVersion);

            // Ocultar el modal después de un tiempo
            setTimeout(() => {
                hideUpdateModal();
            }, 2000);

        } catch (installError) {
            console.error('Error al instalar APK:', installError);
            updateModal.querySelector('.update-message').textContent = '❌ Error al instalar actualización';
            updateModal.querySelector('.update-button').textContent = 'Reintentar';
            updateModal.querySelector('.update-button').style.display = 'block';
        }

    } catch (error) {
        console.error('Error durante el proceso de actualización:', error);
        updateModal.querySelector('.update-message').textContent = `❌ Error: ${error.message}`;
        updateModal.querySelector('.update-button').textContent = 'Reintentar';
        updateModal.querySelector('.update-button').style.display = 'block';
    } finally {
        isUpdating = false;
    }
}

// Función para mostrar el modal de actualización
function showUpdateModal(serverVersion) {
    // Verificar si el modal ya existe
    let updateModal = document.getElementById('ota-update-modal');
    if (!updateModal) {
        // Crear el modal
        updateModal = document.createElement('div');
        updateModal.id = 'ota-update-modal';
        updateModal.className = 'ota-update-modal';
        updateModal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h2>⚠️ ACTUALIZACIÓN CRÍTICA DETECTADA</h2>
                    <button class="close-button">×</button>
                </div>
                <div class="modal-body">
                    <p class="update-message">Descargando núcleo v${serverVersion.version}...</p>
                    <div class="progress-container">
                        <div class="progress-bar"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="update-button" style="display: none;">Reiniciar ahora</button>
                </div>
            </div>
        `;

        // Agregar al cuerpo
        document.body.appendChild(updateModal);

        // Estilos CSS para el modal
        const style = document.createElement('style');
        style.textContent = `
            .ota-update-modal {
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

            .update-message {
                color: var(--text-primary);
                font-size: 1rem;
                margin-bottom: 15px;
                text-align: center;
            }

            .progress-container {
                width: 100%;
                height: 8px;
                background-color: var(--border-color);
                border-radius: 4px;
                margin-bottom: 15px;
                overflow: hidden;
            }

            .progress-bar {
                height: 100%;
                width: 0%;
                background-color: var(--accent-color);
                transition: width 0.3s ease;
            }

            .modal-footer {
                display: flex;
                justify-content: center;
            }

            .update-button {
                background-color: var(--accent-color);
                color: var(--background-primary);
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 1rem;
                cursor: pointer;
                transition: background-color 0.2s;
            }

            .update-button:hover {
                background-color: var(--accent-secondary);
            }
        `;

        document.head.appendChild(style);
    }

    // Mostrar el modal
    updateModal.style.display = 'flex';

    // Event listener para cerrar el modal
    const closeButton = updateModal.querySelector('.close-button');
    if (closeButton) {
        closeButton.addEventListener('click', hideUpdateModal);
    }

    // Event listener para el botón de reinicio
    const updateButton = updateModal.querySelector('.update-button');
    if (updateButton) {
        updateButton.addEventListener('click', () => {
            window.location.reload();
        });
    }

    // Mostrar mensaje inicial
    updateModal.querySelector('.update-message').textContent = `🔄 Actualización disponible: v${serverVersion.version}`;
}

// Función para ocultar el modal de actualización
function hideUpdateModal() {
    const updateModal = document.getElementById('ota-update-modal');
    if (updateModal) {
        updateModal.style.display = 'none';
    }
}

// Función para bloquear la interfaz durante la actualización
function lockInterface() {
    // Deshabilitar todos los botones y enlaces
    document.querySelectorAll('button, a, input, select').forEach(el => {
        el.style.pointerEvents = 'none';
        el.style.opacity = '0.5';
    });

    // Mostrar overlay de bloqueo
    let lockOverlay = document.getElementById('interface-lock-overlay');
    if (!lockOverlay) {
        lockOverlay = document.createElement('div');
        lockOverlay.id = 'interface-lock-overlay';
        lockOverlay.className = 'interface-lock-overlay';
        lockOverlay.innerHTML = `
            <div class="lock-message">
                <div class="lock-icon">🔒</div>
                <p>Actualizando sistema... Por favor espere</p>
            </div>
        `;

        document.body.appendChild(lockOverlay);

        // Estilos CSS para el overlay
        const style = document.createElement('style');
        style.textContent = `
            .interface-lock-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                z-index: 9998;
                display: flex;
                justify-content: center;
                align-items: center;
            }

            .lock-message {
                text-align: center;
                color: var(--text-primary);
                font-size: 1.1rem;
            }

            .lock-icon {
                font-size: 2rem;
                margin-bottom: 10px;
            }
        `;

        document.head.appendChild(style);
    }
}

// Función para desbloquear la interfaz
function unlockInterface() {
    // Habilitar todos los botones y enlaces
    document.querySelectorAll('button, a, input, select').forEach(el => {
        el.style.pointerEvents = '';
        el.style.opacity = '';
    });

    // Ocultar overlay de bloqueo
    const lockOverlay = document.getElementById('interface-lock-overlay');
    if (lockOverlay) {
        lockOverlay.remove();
    }
}

// Función para inicializar el sistema de actualización OTA
function initOTAUpdater() {
    // Verificar si ya hay un intervalo activo
    if (updateCheckIntervalId) {
        clearInterval(updateCheckIntervalId);
    }

    // Obtener la versión local
    const localVersion = getLocalVersion();

    // Verificar si la versión local es válida (mayor que la mínima)
    const localVersionParts = localVersion.version.split('.').map(Number);
    const minVersionParts = MINIMUM_UPDATE_VERSION.split('.').map(Number);

    let isValidLocalVersion = true;
    for (let i = 0; i < Math.min(localVersionParts.length, minVersionParts.length); i++) {
        if (localVersionParts[i] < minVersionParts[i]) {
            isValidLocalVersion = false;
            break;
        } else if (localVersionParts[i] > minVersionParts[i]) {
            break;
        }
    }

    // Si la versión local no es válida, forzar una verificación de actualización
    if (!isValidLocalVersion) {
        console.log('🔄 Versión local no válida. Forzando verificación de actualización...');
        checkForUpdates();
    }

    // Iniciar intervalo para verificar actualizaciones periódicamente
    updateCheckIntervalId = setInterval(checkForUpdates, UPDATE_CHECK_INTERVAL);

    // Verificar actualizaciones inmediatamente al cargar la página
    checkForUpdates();

    // Exportar funciones para que puedan ser usadas desde otros módulos
    return {
        checkForUpdates,
        triggerUpdateProcess,
        lockInterface,
        unlockInterface
    };
}

// Inicializar el módulo cuando la página esté lista
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar el sistema de actualización OTA
    window.otaUpdater = initOTAUpdater();

    // Bloquear la interfaz si hay una actualización en progreso
    // Esto se manejará desde el módulo principal cuando se detecte una actualización
});