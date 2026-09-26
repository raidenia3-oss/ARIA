/**
 * Interceptor de autenticación para peticiones HTTP
 * Añade automáticamente el token JWT a las cabeceras de las peticiones
 */
import { getTokenSecurely, removeTokenSecurely } from './secureStorage.js';
import { showErrorMessage, showSuccessMessage } from './biometricAuth.js';

// Configuración de la API
const API_BASE_URL = 'https://api.aura-system.com';
const AUTH_ENDPOINT = '/api/auth/biometric';
const VALIDATE_ENDPOINT = '/api/auth/validate';

// Función para configurar el interceptor global
async function configureAuthInterceptor() {
  try {
    // Obtener el token almacenado
    const token = await getTokenSecurely();

    if (token) {
      // Configurar interceptor para añadir el token a todas las peticiones
      fetch.addEventListener('request', async (event) => {
        // No añadir token a endpoints de autenticación
        if (event.request.url.includes(AUTH_ENDPOINT) ||
            event.request.url.includes(VALIDATE_ENDPOINT)) {
          return;
        }

        try {
          // Validar el token antes de cada petición (cada 5 minutos)
          const lastValidation = sessionStorage.getItem('lastTokenValidation');
          const now = new Date().getTime();
          const fiveMinutes = 5 * 60 * 1000;

          if (!lastValidation || (now - lastValidation > fiveMinutes)) {
            const validationResponse = await fetch(API_BASE_URL + VALIDATE_ENDPOINT, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              cache: 'no-store'
            });

            if (!validationResponse.ok) {
              // Token inválido, eliminar y bloquear acceso
              await removeTokenSecurely();
              const errorData = await validationResponse.json();
              showErrorMessage(errorData.message || 'Su sesión ha expirado');
              window.location.href = '/lockscreen.html';
              return;
            }

            // Actualizar tiempo de última validación
            sessionStorage.setItem('lastTokenValidation', now.toString());
          }

          // Añadir el token a la petición
          event.request.headers.set('Authorization', `Bearer ${token}`);
        } catch (networkError) {
          console.error('Error de red:', networkError);
          showErrorMessage('Error de conexión con el servidor. Por favor verifique su conexión a internet.');
          // Redirigir a pantalla de bloqueo después de 10 segundos
          setTimeout(() => {
            window.location.href = '/lockscreen.html';
          }, 10000);
        }
      });

      // Configurar interceptor para manejar errores de respuesta
      fetch.addEventListener('response', async (event) => {
        if (!event.response.ok) {
          try {
            const responseData = await event.response.json();
            if (event.response.status === 403) {
              // Token inválido o expirado
              showErrorMessage('Su sesión ha expirado. Por favor autentíquese nuevamente.');
              window.location.href = '/lockscreen.html';
            } else if (event.response.status === 401) {
              // No autorizado
              showErrorMessage('No autorizado. Por favor autentíquese.');
              window.location.href = '/lockscreen.html';
            } else if (event.response.status === 400) {
              // Error de solicitud
              showErrorMessage(responseData.message || 'Error en la solicitud');
            } else {
              // Otros errores
              showErrorMessage(responseData.message || 'Error del servidor');
            }
          } catch (error) {
            console.error('Error procesando respuesta:', error);
            showErrorMessage('Error del servidor. Por favor intente nuevamente.');
          }
        }
      });

      console.log('Interceptor de autenticación configurado correctamente');
      return true;
    } else {
      console.log('No se encontró token almacenado');
      return false;
    }
  } catch (error) {
    console.error('Error configurando interceptor de autenticación:', error);
    throw error;
  }
}

// Función para inicializar el sistema de autenticación
async function initAuthSystem() {
  try {
    // Configurar el interceptor
    await configureAuthInterceptor();

    // Verificar si hay token válido
    const token = await getTokenSecurely();
    if (!token) {
      // Redirigir a pantalla de autenticación
      window.location.href = '/auth.html';
    }

    return true;
  } catch (error) {
    console.error('Error inicializando sistema de autenticación:', error);
    throw error;
  }
}

// Exportar funciones públicas
export {
  configureAuthInterceptor,
  initAuthSystem
};