# Configuración de IP Local en el Dispositivo Móvil

Este documento describe cómo configurar la IP local en el dispositivo móvil para permitir la comunicación con el servidor central del ecosistema AURA/AME.

## 🌐 Contexto

Para que las aplicaciones móviles (App Maid y APK AME) puedan comunicarse con el servidor central, es necesario configurar correctamente la IP local del dispositivo móvil. Esto es especialmente importante cuando el servidor central está en una red local (ej: `192.168.x.x`).

## 📱 Configuración de la IP Local

### 1. Obtener la IP Local del Servidor Central

Primero, debes conocer la IP local del servidor central (PC):

1. **En Windows**:

   ```bash
   ipconfig
   ```

   Busca la dirección IPv4 en la interfaz de red que está conectada a la misma red que tu dispositivo móvil.

2. **En Linux/Mac**:
   ```bash
   ifconfig
   ```
   o
   ```bash
   ip a
   ```
   Busca la dirección IPv4 en la interfaz de red activa.

### 2. Configurar la IP Local en el Dispositivo Móvil

#### Para App Maid:

1. Abre la aplicación App Maid en tu dispositivo móvil.
2. Ve a la sección de configuración de red.
3. Ingresa la IP local del servidor central en el campo correspondiente.
   - Ejemplo: `http://192.168.1.100:8000`

#### Para APK AME:

1. Abre la aplicación APK AME en tu dispositivo móvil.
2. Ve a la configuración de la aplicación.
3. Busca la opción de configuración de red o servidor.
4. Ingresa la IP local del servidor central.
   - Ejemplo: `http://192.168.1.100:8000`

### 3. Configuración en el Archivo `capacitor.config.ts`

El archivo `capacitor.config.ts` en el proyecto de la APK debe configurarse con la IP local correcta:

```typescript
server: {
  androidScheme: 'http', // Usa http para redes locales
  url: 'http://192.168.1.100:8000', // Cambia esto por la IP de tu servidor
  cleartext: true // Permite conexiones no seguras para redes locales
}
```

## 🔄 Configuración de la Red Local

### 1. Configuración del Router

Asegúrate de que tu router esté configurado correctamente para permitir el acceso a la IP local del servidor central.

- **Habilitar el acceso a puertos**: Asegúrate de que el puerto `8000` (o el puerto que uses para el servidor central) esté abierto en el router.

### 2. Conexión a la Misma Red

- Asegúrate de que tanto el servidor central como el dispositivo móvil estén conectados a la misma red Wi-Fi.

### 3. Configuración de Firewall

- **En el servidor central**: Asegúrate de que el firewall permita conexiones entrantes desde dispositivos en la misma red local.

## 📌 Solución de Problemas

### 1. No se puede conectar al servidor

- Verifica que ambos dispositivos estén en la misma red.
- Asegúrate de que la IP local sea correcta.
- Verifica que el servidor central esté en ejecución y escuchando en la IP correcta.

### 2. Conexión lenta o inestable

- Verifica que no haya interferencias en la red Wi-Fi.
- Prueba con un cable Ethernet para el servidor central si es posible.
- Asegúrate de que no haya otros dispositivos consumiendo ancho de banda.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/04_Apps_Móviles]]
- [[02_Configuracion/01_API_Keys_OpenRouter]]
- [[02_Configuracion/03_Instalacion_Termux]]

## 📌 Notas Importantes

- **Seguridad**: Nunca expongas la IP local a Internet sin protección adicional.
- **Uso legítimo**: Esta configuración es solo para uso en redes locales y auditoría de infraestructura propia.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Alternativa**: Si necesitas acceso remoto, considera usar un túnel seguro como Cloudflare Tunnel (configurado en `setup_cloudflare_tunnel.bat`).

## 📝 Ejemplo de Configuración Completa

1. **Servidor Central (PC)**:
   - IP local: `192.168.1.100`
   - Puerto: `8000`
   - Servidor en ejecución: `python core/server.py`

2. **Dispositivo Móvil**:
   - Configuración de App Maid: `http://192.168.1.100:8000`
   - Configuración de APK AME: `http://192.168.1.100:8000` en `capacitor.config.ts`

3. **Router**:
   - Puerto 8000 abierto para la IP `192.168.1.100`
   - Ambos dispositivos en la misma red Wi-Fi
