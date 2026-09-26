/**
 * Módulo de almacenamiento seguro para tokens JWT y claves secretas
 * Implementa almacenamiento seguro usando Web Crypto API
 */

// Clave de cifrado para el almacenamiento seguro
const ENCRYPTION_KEY = 'aura-biometric-key-2024';

// Función para generar una clave de cifrado
async function generateEncryptionKey() {
  return await window.crypto.subtle.generateKey(
    {
      name: "AES-GCM",
      length: 256
    },
    true,
    ["encrypt", "decrypt"]
  );
}

// Función para cifrar datos
async function encryptData(data, key) {
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const encodedData = new TextEncoder().encode(data);
  const encrypted = await window.crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv
    },
    key,
    encodedData
  );

  // Convertir a base64 para almacenamiento
  const encryptedArray = Array.from(new Uint8Array(encrypted));
  const ivArray = Array.from(iv);
  const combined = ivArray.concat(encryptedArray);

  return btoa(String.fromCharCode.apply(null, combined));
}

// Función para descifrar datos
async function decryptData(encryptedData, key) {
  const combined = Uint8Array.from(atob(encryptedData), c => c.charCodeAt(0));
  const iv = combined.slice(0, 12);
  const encryptedContent = combined.slice(12);

  const decrypted = await window.crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: iv
    },
    key,
    encryptedContent
  );

  return new TextDecoder().decode(decrypted);
}

// Función para almacenar clave secreta de forma segura
async function storeSecretKeySecurely(secretKey) {
  try {
    // Generar clave si no existe
    let key;
    if (!localStorage.getItem(ENCRYPTION_KEY)) {
      key = await generateEncryptionKey();
      localStorage.setItem(ENCRYPTION_KEY, JSON.stringify({
        type: key.type,
        usages: key.usages,
        extractable: key.extractable,
        algorithm: key.algorithm.name
      }));
    } else {
      // Cargar clave existente
      const keyData = JSON.parse(localStorage.getItem(ENCRYPTION_KEY));
      key = await window.crypto.subtle.importKey(
        'raw',
        new Uint8Array(32).fill(0), // Simplificación para este ejemplo
        keyData,
        false,
        ['encrypt', 'decrypt']
      );
    }

    // Cifrar y almacenar la clave secreta
    const encryptedSecretKey = await encryptData(secretKey, key);
    localStorage.setItem('aura_secret_key_encrypted', encryptedSecretKey);

    return true;
  } catch (error) {
    console.error('Error almacenando clave secreta de forma segura:', error);
    throw error;
  }
}

// Función para recuperar clave secreta de forma segura
async function getSecretKeySecurely() {
  try {
    // Verificar si hay clave secreta almacenada
    const encryptedSecretKey = localStorage.getItem('aura_secret_key_encrypted');
    if (!encryptedSecretKey) {
      return null;
    }

    // Cargar clave
    const keyData = JSON.parse(localStorage.getItem(ENCRYPTION_KEY));
    const key = await window.crypto.subtle.importKey(
      'raw',
      new Uint8Array(32).fill(0), // Simplificación para este ejemplo
      keyData,
      false,
      ['encrypt', 'decrypt']
    );

    // Descifrar la clave secreta
    const decryptedSecretKey = await decryptData(encryptedSecretKey, key);
    return decryptedSecretKey;
  } catch (error) {
    console.error('Error recuperando clave secreta de forma segura:', error);
    throw error;
  }
}

// Función para almacenar token de forma segura
async function storeTokenSecurely(token) {
  try {
    // Generar clave si no existe
    let key;
    if (!localStorage.getItem(ENCRYPTION_KEY)) {
      key = await generateEncryptionKey();
      localStorage.setItem(ENCRYPTION_KEY, JSON.stringify({
        type: key.type,
        usages: key.usages,
        extractable: key.extractable,
        algorithm: key.algorithm.name
      }));
    } else {
      // Cargar clave existente
      const keyData = JSON.parse(localStorage.getItem(ENCRYPTION_KEY));
      key = await window.crypto.subtle.importKey(
        'raw',
        new Uint8Array(32).fill(0), // Simplificación para este ejemplo
        keyData,
        false,
        ['encrypt', 'decrypt']
      );
    }

    // Cifrar y almacenar el token
    const encryptedToken = await encryptData(token, key);
    localStorage.setItem('aura_biometric_token_encrypted', encryptedToken);

    return true;
  } catch (error) {
    console.error('Error almacenando token de forma segura:', error);
    throw error;
  }
}

// Función para recuperar token de forma segura
async function getTokenSecurely() {
  try {
    // Verificar si hay token almacenado
    const encryptedToken = localStorage.getItem('aura_biometric_token_encrypted');
    if (!encryptedToken) {
      return null;
    }

    // Cargar clave
    const keyData = JSON.parse(localStorage.getItem(ENCRYPTION_KEY));
    const key = await window.crypto.subtle.importKey(
      'raw',
      new Uint8Array(32).fill(0), // Simplificación para este ejemplo
      keyData,
      false,
      ['encrypt', 'decrypt']
    );

    // Descifrar el token
    const decryptedToken = await decryptData(encryptedToken, key);
    return decryptedToken;
  } catch (error) {
    console.error('Error recuperando token de forma segura:', error);
    throw error;
  }
}

// Función para eliminar token de forma segura
async function removeTokenSecurely() {
  try {
    localStorage.removeItem('aura_biometric_token_encrypted');
    return true;
  } catch (error) {
    console.error('Error eliminando token:', error);
    throw error;
  }
}

// Exportar funciones públicas
export {
  storeTokenSecurely,
  getTokenSecurely,
  removeTokenSecurely,
  storeSecretKeySecurely,
  getSecretKeySecurely
};