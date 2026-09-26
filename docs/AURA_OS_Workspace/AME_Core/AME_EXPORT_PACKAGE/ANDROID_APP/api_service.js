/**
 * Servicio de red para manejar peticiones HTTP hacia el backend AURA.
 * Incluye autenticación JWT automática en las cabeceras.
 */

// Configuración del endpoint desde el archivo .env
const env = {
    AURA_ENDPOINT: process.env.AURA_ENDPOINT || 'http://localhost:5000',
    REQUEST_TIMEOUT: parseInt(process.env.REQUEST_TIMEOUT) || 10000
};

// Función para obtener el token JWT almacenado
function getJwtToken() {
    return localStorage.getItem('aura_jwt_token');
}

// Función para añadir el token a las cabeceras de la petición
function addAuthHeader(headers = {}) {
    const token = getJwtToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

// Función para realizar peticiones HTTP
async function makeRequest(url, options = {}) {
    const fullUrl = `${env.AURA_ENDPOINT}${url}`;

    // Configuración base de la petición
    const defaultOptions = {
        method: options.method || 'GET',
        headers: addAuthHeader(options.headers || {}),
        timeout: env.REQUEST_TIMEOUT,
    };

    // Si hay cuerpo en la petición, añadirlo
    if (options.body) {
        defaultOptions.body = options.body;
        defaultOptions.headers['Content-Type'] = 'application/json';
    }

    // Realizar la petición
    try {
        const response = await fetch(fullUrl, defaultOptions);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.message || 'Unknown error'}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Error en la petición:', error);
        throw error;
    }
}

// Funciones específicas para diferentes métodos HTTP
export async function get(url, options = {}) {
    return makeRequest(url, { ...options, method: 'GET' });
}

export async function post(url, body, options = {}) {
    return makeRequest(url, { ...options, method: 'POST', body: JSON.stringify(body) });
}

export async function put(url, body, options = {}) {
    return makeRequest(url, { ...options, method: 'PUT', body: JSON.stringify(body) });
}

export async function deleteRequest(url, options = {}) {
    return makeRequest(url, { ...options, method: 'DELETE' });
}

// Función para probar la conexión al servidor (ping)
export async function pingServer() {
    try {
        const response = await fetch(`${env.AURA_ENDPOINT}/api/health`, {
            method: 'GET',
            headers: addAuthHeader(),
            timeout: env.REQUEST_TIMEOUT
        });

        if (!response.ok) {
            throw new Error('Servidor no respondió correctamente');
        }

        const data = await response.json();
        return { success: true, data };
    } catch (error) {
        console.error('Error al hacer ping al servidor:', error);
        return { success: false, error: error.message };
    }
}