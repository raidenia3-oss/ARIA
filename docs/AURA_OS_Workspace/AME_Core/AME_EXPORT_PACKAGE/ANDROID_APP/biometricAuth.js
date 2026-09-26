/**
 * Módulo para manejar la autenticación biométrica en la app AME.
 * Integra el plugin @capacitor-community/biometric-auth para validación biométrica.
 */

// Función para autenticar usando biometría
async function authenticateBiometrically() {
    return new Promise(async (resolve, reject) => {
        try {
            // Verificar si Capacitor está disponible
            if (!window.Capacitor) {
                throw new Error("Capacitor no está disponible");
            }

            // Verificar si el plugin de biometría está disponible
            if (!window.Plugins || !window.Plugins.BiometricAuth) {
                throw new Error("Plugin de autenticación biométrica no disponible");
            }

            // Configuración para el plugin de biometría
            const options = {
                title: 'Autenticación Biométrica',
                subtitle: 'Por favor, autentíquese',
                description: 'Se requiere autenticación biométrica para acceder a AURA',
                cancelLabel: 'Cancelar',
                fallbackLabel: 'Usar contraseña',
                disableDeviceFallback: false,
            };

            // Realizar la autenticación biométrica
            const result = await window.Plugins.BiometricAuth.authenticate(options);

            if (result.response.success) {
                resolve(result);
            } else {
                throw new Error("Autenticación biométrica fallida");
            }
        } catch (error) {
            console.error("Error en autenticación biométrica:", error);
            reject(error);
        }
    });
}

// Función para obtener un token JWT del backend
async function getJwtToken(userId) {
    try {
        const response = await fetch('http://localhost:5000/api/auth/biometric', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_id: userId })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`Error al obtener el token JWT: ${errorData.message || 'Error desconocido'}`);
        }

        const data = await response.json();
        return data.token;
    } catch (error) {
        console.error('Error al obtener el token JWT:', error);
        throw error;
    }
}

// Función principal para manejar el flujo de autenticación
async function handleBiometricAuth() {
    try {
        // Autenticación biométrica
        const authResult = await authenticateBiometrically();
        console.log('Autenticación biométrica exitosa:', authResult);

        // Obtener token JWT del backend con el user_id del resultado biométrico
        const userId = authResult.userId || 'default_user';
        const token = await getJwtToken(userId);
        console.log('Token JWT obtenido:', token);

        // Almacenar el token de forma segura
        localStorage.setItem('aura_jwt_token', token);

        // Retornar el token para su uso en las peticiones HTTP
        return token;
    } catch (error) {
        console.error('Error en el flujo de autenticación:', error);
        throw error;
    }
}

// Función para mostrar mensaje de error al usuario
function showErrorToUser(message) {
    alert(`Error: ${message}`);
    console.error('Error mostrado al usuario:', message);
}

// Ejecutar el flujo de autenticación al cargar la app
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const token = await handleBiometricAuth();
        console.log('Autenticación completada. Token:', token);
    } catch (error) {
        showErrorToUser(error.message);
        console.error('Error al iniciar autenticación:', error);
    }
});

// Función para añadir el token a las cabeceras de las peticiones HTTP
function addAuthHeader(xhr) {
    const token = localStorage.getItem('aura_jwt_token');
    if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
}

// Configurar el evento para añadir el token a las peticiones AJAX
document.addEventListener('DOMContentLoaded', () => {
    // Sobrescribir fetch para añadir el token automáticamente
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const [input, init] = args;
        const headers = new Headers(init ? init.headers : {});
        const token = localStorage.getItem('aura_jwt_token');
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
        }
        const response = await originalFetch(input, { ...init, headers });
        return response;
    };

    // Sobrescribir XMLHttpRequest para añadir el token
    const originalXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        this.addEventListener('loadstart', () => {
            addAuthHeader(this);
        });
        originalXHROpen.apply(this, arguments);
    };
});