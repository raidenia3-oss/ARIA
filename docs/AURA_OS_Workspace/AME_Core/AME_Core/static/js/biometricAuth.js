/**
 * Módulo de autenticación biométrica para AURA Mobile
 * Implementa el flujo de autenticación biométrica y manejo de tokens JWT
 * Basado en @capgo/capacitor-native-biometric
 */
import { NativeBiometric } from "@capgo/capacitor-native-biometric";
import { getTokenSecurely, removeTokenSecurely, storeTokenSecurely } from "./secureStorage.js";

// Configuración de la API
const API_BASE_URL = window.location.origin || "https://api.aura-system.com";
const AUTH_ENDPOINT = "/api/auth/biometric";
const VALIDATE_ENDPOINT = "/api/auth/validate";

// Función para mostrar mensaje de error temporal
function showErrorMessage(message) {
    let errorElement = document.getElementById("aura-error-message");
    if (errorElement) {
        errorElement.textContent = message;
        return;
    }
    errorElement = document.createElement("div");
    errorElement.id = "aura-error-message";
    errorElement.style.cssText =
        "position:fixed;top:20px;right:20px;padding:15px;background:#ff4444;color:white;border-radius:5px;z-index:9999;box-shadow:0 2px 10px rgba(0,0,0,0.2);max-width:300px;text-align:center;font-size:14px;line-height:1.4;transition:opacity 0.3s ease";
    errorElement.textContent = message;
    document.body.appendChild(errorElement);
    setTimeout(() => {
        errorElement.style.opacity = "0";
        setTimeout(() => document.body.removeChild(errorElement), 300);
    }, 5000);
}

// Función para mostrar mensaje de éxito
function showSuccessMessage(message) {
    let successElement = document.getElementById("aura-success-message");
    if (successElement) {
        successElement.textContent = message;
        return;
    }
    successElement = document.createElement("div");
    successElement.id = "aura-success-message";
    successElement.style.cssText =
        "position:fixed;top:20px;right:20px;padding:15px;background:#4CAF50;color:white;border-radius:5px;z-index:9999;box-shadow:0 2px 10px rgba(0,0,0,0.2);max-width:300px;text-align:center;font-size:14px;line-height:1.4;transition:opacity 0.3s ease";
    successElement.textContent = message;
    document.body.appendChild(successElement);
    setTimeout(() => {
        successElement.style.opacity = "0";
        setTimeout(() => document.body.removeChild(successElement), 300);
    }, 5000);
}

// Función para configurar el token para peticiones HTTP
function configureAuthToken(token) {
    if (!window._auraAuthPatched) {
        window._auraAuthPatched = true;
        const originalFetch = window.fetch;
        window.fetch = async function (url, options = {}) {
            if (
                typeof url === "string" &&
                !url.includes(AUTH_ENDPOINT) &&
                !url.includes(VALIDATE_ENDPOINT)
            ) {
                options.headers = { ...options.headers, Authorization: `Bearer ${token}` };
            }
            return originalFetch(url, options);
        };
    }
}

// Verificar disponibilidad de biometría
async function checkBiometricAvailability() {
    try {
        const result = await NativeBiometric.isAvailable();
        if (!result.isAvailable) {
            showErrorMessage("Su dispositivo no soporta autenticación biométrica.");
            throw new Error("Dispositivo no soporta autenticación biométrica");
        }
        return result;
    } catch (error) {
        console.error("Error verificando disponibilidad biométrica:", error);
        showErrorMessage("Error verificando autenticación biométrica.");
        throw error;
    }
}

// Iniciar autenticación biométrica
async function authenticateBiometrically() {
    try {
        // Verificar si ya hay un token válido almacenado
        const storedToken = await getTokenSecurely();
        if (storedToken) {
            try {
                const response = await fetch(`${API_BASE_URL}${VALIDATE_ENDPOINT}`, {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${storedToken}`,
                        "Content-Type": "application/json",
                    },
                });
                if (response.ok) {
                    console.log("Token válido encontrado en almacenamiento");
                    configureAuthToken(storedToken);
                    return storedToken;
                } else {
                    await removeTokenSecurely();
                    throw new Error("Token JWT inválido");
                }
            } catch (error) {
                console.error("Error validando token almacenado:", error);
                throw error;
            }
        }

        // Verificar disponibilidad de biometría
        await checkBiometricAvailability();

        // Iniciar autenticación biométrica con @capgo/capacitor-native-biometric
        const result = await NativeBiometric.verifyIdentity({
            reason: "AURA requiere autenticación biométrica para acceder a sus funciones",
            title: "Autenticación Biométrica",
            subtitle: "Accede a AURA con tu huella o rostro",
            description: "Por favor autentíquese para continuar",
            maxAttempts: 3,
        });

        if (result && result.verified) {
            // Autenticación exitosa, obtener token JWT
            try {
                const tokenResponse = await fetch(`${API_BASE_URL}${AUTH_ENDPOINT}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: "architect" }),
                });

                if (tokenResponse.ok) {
                    const data = await tokenResponse.json();
                    const jwtToken = data.token;

                    showSuccessMessage("Autenticación biométrica exitosa");
                    await storeTokenSecurely(jwtToken);
                    configureAuthToken(jwtToken);
                    return jwtToken;
                } else {
                    const errorData = await tokenResponse.json();
                    showErrorMessage(errorData.message || "Error obteniendo token JWT");
                    throw new Error("Error obteniendo token JWT");
                }
            } catch (networkError) {
                console.error("Error de red obteniendo token JWT:", networkError);
                showErrorMessage("Error de conexión con el servidor.");
                throw new Error("Error de red obteniendo token JWT");
            }
        } else {
            showErrorMessage("Autenticación cancelada por el usuario");
            throw new Error("Autenticación cancelada");
        }
    } catch (biometricError) {
        console.error("Error en autenticación biométrica:", biometricError);
        if (
            biometricError.message?.includes("not enrolled") ||
            biometricError.message?.includes("not available")
        ) {
            showErrorMessage("No tiene configurada ninguna opción biométrica en su dispositivo.");
        } else if (biometricError.message?.includes("cancel")) {
            showErrorMessage("Autenticación cancelada por el usuario");
        } else {
            showErrorMessage("Error en la autenticación biométrica.");
        }
        throw biometricError;
    }
}

// Inicializar el sistema de autenticación
async function initBiometricAuth() {
    try {
        const token = await authenticateBiometrically();
        if (token) {
            console.log("Autenticación biométrica exitosa.");
            return true;
        }
        console.log("Autenticación biométrica fallida");
        return false;
    } catch (error) {
        console.error("Error inicializando autenticación biométrica:", error);
        window.location.href = window.location.origin + "/lockscreen.html";
        return false;
    }
}

// Exportar funciones públicas
export {
    authenticateBiometrically,
    checkBiometricAvailability,
    configureAuthToken,
    initBiometricAuth,
    showErrorMessage,
    showSuccessMessage,
};
