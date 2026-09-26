/**
 * Interceptor de autenticación para WebSocket
 * Añade automáticamente el token JWT a las conexiones WebSocket
 */
import { getTokenSecurely, removeTokenSecurely } from './secureStorage.js';
import { showErrorMessage } from './biometricAuth.js';

// Configuración de WebSocket
const WS_BASE_URL = 'wss://ws.aura-system.com';
const WS_AUTH_ENDPOINT = '/ws/auth';

  // Función para configurar el interceptor WebSocket
  async function configureWSAuthInterceptor() {
    // ===== INTERCEPTOR GLOBAL DE FETCH =====
    // Wrapper que maneja timeouts, reintentos y cabeceras CORS
    if (!window._auraFetchPatched) {
      window._auraFetchPatched = true;
      const originalFetch = window.fetch;
      window.fetch = async function(url, options = {}) {
        const AURA_TIMEOUT = 30000; // 30s timeout global
        const AURA_MAX_RETRIES = 2;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), AURA_TIMEOUT);
        const baseHeaders = {
          'X-AURA-Client': navigator.userAgent || 'AURA-Mobile',
          'X-Requested-With': 'AURA-AME',
        };
        // Integrar con el sistema de auth token si está disponible
        try {
          const token = await getTokenSecurely();
          if (token) baseHeaders['Authorization'] = `Bearer ${token}`;
        } catch (e) { /* sin token */ }
        let lastError = null;
        for (let attempt = 0; attempt <= AURA_MAX_RETRIES; attempt++) {
          try {
            const enhancedOptions = {
              ...options,
              signal: controller.signal,
              headers: { ...baseHeaders, ...(options.headers || {}) },
              credentials: 'include',
              mode: 'cors',
            };
            const response = await originalFetch(url, enhancedOptions);
            clearTimeout(timeoutId);
            return response;
          } catch (err) {
            lastError = err;
            if (err.name === 'AbortError') {
              console.warn(`[AURA Network] Timeout (${AURA_TIMEOUT}ms) en ${url} (intento ${attempt+1})`);
              if (attempt < AURA_MAX_RETRIES) {
                await new Promise(r => setTimeout(r, 1000 * (attempt + 1))); // backoff 1s, 2s
                continue;
              }
            }
            console.error(`[AURA Network] Falló ${url}: ${err.message}`);
          }
        }
        clearTimeout(timeoutId);
        throw lastError || new Error('Failed to fetch after retries');
      };
    }

    try {
      // Obtener el token almacenado
      const token = await getTokenSecurely();

    if (token) {
      // Función para validar el token antes de conectar
      const validateTokenBeforeConnect = async (wsUrl) => {
        try {
          // Validar el token con el servidor
          const response = await fetch('https://api.aura-system.com/api/auth/validate', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            cache: 'no-store'
          });

          if (!response.ok) {
            // Token inválido, cerrar conexión y bloquear acceso
            throw new Error('Token JWT inválido');
          }

          // Si el token es válido, añadirlo a la URL del WebSocket
          const url = new URL(wsUrl);
          url.searchParams.set('token', token);
          return url.toString();
        } catch (error) {
          console.error('Error validando token para WebSocket:', error);
          throw error;
        }
      };

      // Sobrescribir el constructor de WebSocket para añadir el token
      const OriginalWebSocket = window.WebSocket;
      window.WebSocket = class extends OriginalWebSocket {
        constructor(url, protocols) {
          // Validar el token antes de conectar
          validateTokenBeforeConnect(url)
            .then(validUrl => {
              // Conectar con la URL validada
              super(validUrl, protocols);

              // Configurar manejador de errores para la conexión WebSocket
              this.onerror = (event) => {
                console.error('Error en WebSocket:', event);
                if (event.message.includes('403') || event.message.includes('Forbidden')) {
                  // Token inválido, cerrar conexión y bloquear acceso
                  showErrorMessage('Su sesión ha expirado. Por favor autentíquese nuevamente.');
                  setTimeout(() => {
                    window.location.href = '/lockscreen.html';
                  }, 3000);
                } else {
                  // Otros errores de conexión
                  showErrorMessage('Error de conexión con el servidor WebSocket');
                }
              };

              this.onclose = (event) => {
                console.log('WebSocket cerrado:', event.code, event.reason);
                if (event.code === 4003 || event.code === 4013) {
                  // Código de error relacionado con autenticación
                  showErrorMessage('Su sesión ha expirado. Por favor autentíquese nuevamente.');
                  setTimeout(() => {
                    window.location.href = '/lockscreen.html';
                  }, 3000);
                } else if (event.code === 1006) {
                  // Abrupt closure
                  showErrorMessage('Conexión WebSocket cerrada abruptamente');
                } else {
                  // Otros códigos de cierre
                  showErrorMessage(`Conexión cerrada: ${event.reason || 'Sin motivo'}`);
                }
              };
            })
            .catch(error => {
              console.error('Error conectando a WebSocket:', error);
              if (error.message.includes('NetworkError')) {
                showErrorMessage('Error de red. Por favor verifique su conexión a internet.');
              } else if (error.message.includes('invalid token')) {
                showErrorMessage('Token JWT inválido. Por favor autentíquese nuevamente.');
              } else {
                showErrorMessage('Error conectando a WebSocket. Por favor intente nuevamente.');
              }

              // Redirigir a pantalla de bloqueo después de 5 segundos
              setTimeout(() => {
                window.location.href = '/lockscreen.html';
              }, 5000);
            });
        }
      };

      console.log('Interceptor de autenticación WebSocket configurado correctamente');
      return true;
    } else {
      console.log('No se encontró token almacenado para WebSocket');
      return false;
    }
  } catch (error) {
    console.error('Error configurando interceptor de autenticación WebSocket:', error);
    throw error;
  }
}

// Exportar funciones públicas
export {
  configureWSAuthInterceptor
};