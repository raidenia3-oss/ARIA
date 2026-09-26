/**
 * Módulo de autenticación biométrica para AURA Mobile
 * Implementa el flujo de autenticación biométrica y manejo de tokens JWT
 */
import { Plugins } from '@capacitor/core';
import { storeTokenSecurely, getTokenSecurely, removeTokenSecurely } from './secureStorage.js';
const { BiometricAuth } = Plugins;

// Configuración de la API
const API_BASE_URL = 'https://api.aura-system.com';
const AUTH_ENDPOINT = '/api/auth/biometric';
const VALIDATE_ENDPOINT = '/api/auth/validate';

// Función para mostrar mensaje de error temporal
function showErrorMessage(message) {
  // Verificar si ya existe un mensaje de error
  let errorElement = document.getElementById('aura-error-message');
  if (errorElement) {
    errorElement.textContent = message;
    return;
  }

  // Crear un elemento para mostrar el mensaje
  errorElement = document.createElement('div');
  errorElement.id = 'aura-error-message';
  errorElement.style.position = 'fixed';
  errorElement.style.top = '20px';
  errorElement.style.right = '20px';
  errorElement.style.padding = '15px';
  errorElement.style.backgroundColor = '#ff4444';
  errorElement.style.color = 'white';
  errorElement.style.borderRadius = '5px';
  errorElement.style.zIndex = '9999';
  errorElement.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.2)';
  errorElement.style.maxWidth = '300px';
  errorElement.style.textAlign = 'center';
  errorElement.style.fontSize = '14px';
  errorElement.style.lineHeight = '1.4';
  errorElement.style.transition = 'opacity 0.3s ease';

  errorElement.textContent = message;

  // Añadir al documento
  document.body.appendChild(errorElement);

  // Eliminar después de 5 segundos
  setTimeout(() => {
    errorElement.style.opacity = '0';
    setTimeout(() => {
      document.body.removeChild(errorElement);
    }, 300);
  }, 5000);
}

// Función para mostrar mensaje de éxito
function showSuccessMessage(message) {
  // Verificar si ya existe un mensaje de éxito
  let successElement = document.getElementById('aura-success-message');
  if (successElement) {
    successElement.textContent = message;
    return;
  }

  // Crear un elemento para mostrar el mensaje
  successElement = document.createElement('div');
  successElement.id = 'aura-success-message';
  successElement.style.position = 'fixed';
  successElement.style.top = '20px';
  successElement.style.right = '20px';
  successElement.style.padding = '15px';
  successElement.style.backgroundColor = '#4CAF50';
  successElement.style.color = 'white';
  successElement.style.borderRadius = '5px';
  successElement.style.zIndex = '9999';
  successElement.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.2)';
  successElement.style.maxWidth = '300px';
  successElement.style.textAlign = 'center';
  successElement.style.fontSize = '14px';
  successElement.style.lineHeight = '1.4';
  successElement.style.transition = 'opacity 0.3s ease';

  successElement.textContent = message;

  // Añadir al documento
  document.body.appendChild(successElement);

  // Eliminar después de 5 segundos
  setTimeout(() => {
    successElement.style.opacity = '0';
    setTimeout(() => {
      document.body.removeChild(successElement);
    }, 300);
  }, 5000);
}

// Función para bloquear el acceso en caso de error
function blockAccess(errorMessage) {
  // Mostrar mensaje de error al usuario
  console.error('Error de autenticación:', errorMessage);

  // Redirigir a la pantalla de bloqueo
  window.location.href = '/lockscreen.html';
}

// Función para configurar el token para peticiones HTTP
function configureAuthToken(token) {
  // Configurar interceptores para añadir el token a todas las peticiones
  fetch.addEventListener('request', (event) => {
    if (!event.request.url.includes(AUTH_ENDPOINT) && !event.request.url.includes(VALIDATE_ENDPOINT)) {
      event.request.headers.set('Authorization', `Bearer ${token}`);
    }
  });
}

// Función para verificar disponibilidad de biométrica
async function checkBiometricAvailability() {
  try {
    const isAvailable = await BiometricAuth.isAvailable();
    if (!isAvailable) {
      showErrorMessage('Su dispositivo no soporta autenticación biométrica.');
      alert('Su dispositivo no soporta autenticación biométrica. Por favor use otro método de autenticación.');
      throw new Error('Dispositivo no soporta autenticación biométrica');
    }
    return true;
  } catch (error) {
    console.error('Error verificando disponibilidad biométrica:', error);
    showErrorMessage('Error verificando autenticación biométrica. Por favor intente nuevamente.');
    throw error;
  }
}

// Función para iniciar autenticación biométrica
async function authenticateBiometrically() {
  try {
    // Verificar si ya hay un token válido almacenado
    const storedToken = await getTokenSecurely();
    if (storedToken) {
      try {
        // Validar el token existente
        const response = await fetch(API_BASE_URL + VALIDATE_ENDPOINT, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${storedToken}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          console.log('Token válido encontrado en almacenamiento');
          return storedToken;
        } else {
          // Token inválido, eliminar y mostrar mensaje
          await removeTokenSecurely();
          const errorData = await response.json();
          showErrorMessage(errorData.message || 'Su sesión ha expirado. Por favor autentíquese nuevamente.');
          throw new Error('Token JWT inválido');
        }
      } catch (error) {
        console.error('Error validando token almacenado:', error);
        if (error.message.includes('NetworkError')) {
          showErrorMessage('Error de conexión con el servidor. Por favor verifique su conexión a internet.');
        } else {
          showErrorMessage('Error validando su sesión. Por favor intente nuevamente.');
        }
        throw error;
      }
    }

    // Verificar disponibilidad de biométrica
    await checkBiometricAvailability();

    // Iniciar autenticación biométrica
    const result = await BiometricAuth.authenticate({
      title: 'Autenticación Biométrica',
      subtitle: 'Por favor autentíquese con su huella o rostro',
      cancelTitle: 'Cancelar',
      fallbackTitle: 'Ingresar con contraseña',
      description: 'AURA requiere autenticación biométrica para acceder a sus funciones',
      useFaceAuth: true,
      useFingerprintAuth: true
    });

    if (result.response) {
      // Autenticación exitosa, obtener token JWT
      try {
        const tokenResponse = await fetch(API_BASE_URL + AUTH_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${result.response.token}`
          }
        });

        if (tokenResponse.ok) {
          const data = await tokenResponse.json();
          const jwtToken = data.token;

          // Mostrar mensaje de éxito
          showSuccessMessage('Autenticación biométrica exitosa');

          // Almacenar el token de forma segura
          await storeTokenSecurely(jwtToken);

          // Configurar el token para peticiones futuras
          configureAuthToken(jwtToken);

          return jwtToken;
        } else {
          const errorData = await tokenResponse.json();
          showErrorMessage(errorData.message || 'Error obteniendo token JWT');
          throw new Error('Error obteniendo token JWT');
        }
      } catch (networkError) {
        console.error('Error de red obteniendo token JWT:', networkError);
        if (networkError.message.includes('NetworkError')) {
          showErrorMessage('Error de conexión con el servidor. Por favor verifique su conexión a internet.');
        } else {
          showErrorMessage('Error comunicándose con el servidor. Por favor intente nuevamente.');
        }
        throw new Error('Error de red obteniendo token JWT');
      }
    } else {
      // Autenticación cancelada
      showErrorMessage('Autenticación cancelada por el usuario');
      throw new Error('Autenticación cancelada por el usuario');
    }
  } catch (biometricError) {
    console.error('Error en autenticación biométrica:', biometricError);
    if (biometricError.message.includes('not enrolled')) {
      showErrorMessage('No tiene configurada ninguna opción biométrica en su dispositivo.');
      // Mostrar opción de configuración
      setTimeout(() => {
        alert('Para usar la autenticación biométrica, configure huella dactilar o reconocimiento facial en:\n\n1. Android: Ajustes > Seguridad > Huella o Rostro\n2. iOS: Ajustes > Face ID y código');
      }, 2000);
    } else if (biometricError.message.includes('cancelled') || biometricError.message.includes('operation cancelled')) {
      showErrorMessage('Autenticación cancelada por el usuario');
    } else if (biometricError.message.includes('not supported')) {
      showErrorMessage('Su dispositivo no soporta autenticación biométrica.');
      alert('Su dispositivo no soporta autenticación biométrica. Por favor use otro método de autenticación.');
    } else if (biometricError.message.includes('hardware unavailable')) {
      showErrorMessage('El hardware biométrico no está disponible. Por favor verifique que el sensor esté funcionando.');
    } else {
      showErrorMessage('Error en la autenticación biométrica. Por favor intente nuevamente.');
    }
    throw biometricError;
  }
}

// Función para inicializar el sistema de autenticación
async function initBiometricAuth() {
  try {
    // Intentar autenticación al iniciar la aplicación
    const token = await authenticateBiometrically();

    if (token) {
      console.log('Autenticación biométrica exitosa. Token:', token);
      return true;
    } else {
      console.log('Autenticación biométrica fallida');
      return false;
    }
  } catch (error) {
    console.error('Error inicializando autenticación biométrica:', error);
    blockAccess('No se pudo autenticar. Por favor intente nuevamente.');
    return false;
  }
}

// Exportar funciones públicas
export {
  authenticateBiometrically,
  configureAuthToken,
  initBiometricAuth,
  blockAccess,
  showErrorMessage,
  showSuccessMessage,
  checkBiometricAvailability
};