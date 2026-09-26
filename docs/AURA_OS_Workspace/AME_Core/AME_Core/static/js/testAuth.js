/**
 * Script de prueba para validar el blindaje de red (Zero-Trust)
 * Este script prueba que el middleware de seguridad funcione correctamente.
 */

// Configuración de la API
const API_BASE_URL = 'https://aura-server-01.vercel.app'; // Puerto del webhook de AURA
const TEST_ENDPOINT = '/api/status';

// Función para realizar una petición y mostrar el resultado
async function testRequest(apiKey) {
  try {
    const response = await fetch(API_BASE_URL + TEST_ENDPOINT, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey && { 'x-api-key': apiKey })
      }
    });

    const data = await response.json();
    const status = response.status;

    console.log(`Petición con clave "${apiKey ? 'presente' : 'ausente'}":`);
    console.log(`- Status: ${status}`);
    console.log(`- Respuesta:`, data);
    console.log('----------------------------------------');

    return { status, data };
  } catch (error) {
    console.log(`Petición con clave "${apiKey ? 'presente' : 'ausente'}":`);
    console.log(`- Error: ${error.message}`);
    console.log('----------------------------------------');
    return { error: error.message };
  }
}

// Función principal para ejecutar las pruebas
async function runTests() {
  console.log('🔒 Iniciando pruebas de blindaje de red (Zero-Trust)');
  console.log('----------------------------------------');

  // Prueba 1: Sin clave API (debería fallar con 401)
  console.log('Prueba 1: Petición SIN clave API');
  await testRequest();

  // Prueba 2: Con clave API incorrecta (debería fallar con 401)
  console.log('Prueba 2: Petición CON clave API incorrecta');
  await testRequest('incorrecta');

  // Prueba 3: Con clave API correcta (debería funcionar)
  console.log('Prueba 3: Petición CON clave API correcta');
  const secretKey = '7x!A%3sD0@9kLpQ2rY8bNvE1zF4cG7hJ'; // Clave configurada en el backend
  await testRequest(secretKey);

  console.log('🔍 Pruebas completadas.');
}

// Ejecutar las pruebas
runTests();
