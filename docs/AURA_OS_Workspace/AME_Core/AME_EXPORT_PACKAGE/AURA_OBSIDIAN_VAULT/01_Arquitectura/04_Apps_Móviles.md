# Apps Móviles - Interfaces para el Ecosistema AURA/AME

Este documento describe las aplicaciones móviles que forman parte del ecosistema AURA/AME: **App Maid** y **APK AME**. Ambas aplicaciones permiten interactuar con el servidor central y los modelos de lenguaje desde dispositivos móviles.

## 📱 Aplicaciones Móviles

### 1. App Maid

App Maid es una aplicación para Android que consume los endpoints del servidor central.

- **Funcionalidades principales**:
  - Interfaz de usuario para interactuar con modelos de lenguaje.
  - Consumo del endpoint `POST /v1/chat/completions`.
  - Sincronización de datos con el servidor central.
  - Consulta de estado del agente de Termux mediante `GET /v1/agent/status`.

- **Características**:
  - Diseño minimalista y orientado a la productividad.
  - Integración con servicios de notificación.
  - Soporte para autenticación biométrica.

### 2. APK AME

APK AME es una aplicación móvil nativa que interactúa con el servidor central.

- **Funcionalidades principales**:
  - Interfaz avanzada para gestión de tareas tácticas.
  - Consumo de modelos de lenguaje mediante `POST /v1/chat/completions`.
  - Integración con módulos tácticos (Nmap, OSINT, etc.).
  - Sincronización bidireccional con el servidor central.

- **Características**:
  - Dashboard táctico con visualización de datos en tiempo real.
  - Soporte para comandos de voz y gestos.
  - Integración con servicios de telemetría y alertas.
  - Configuración avanzada de endpoints y modelos.

## 🔄 Flujo de Interacción

1. **Conexión al Servidor Central**:
   - Las aplicaciones establecen conexión con el servidor central usando la URL configurada en `capacitor.config.ts`.

2. **Interacción con Modelos**:
   - Las aplicaciones envían solicitudes a `POST /v1/chat/completions`.
   - Reciben respuestas de los modelos de lenguaje disponibles.

3. **Sincronización de Datos**:
   - Las aplicaciones pueden enviar datos de telemetría y eventos al servidor.
   - Reciben comandos y actualizaciones del servidor.

4. **Consulta de Estado**:
   - Las aplicaciones pueden consultar el estado del agente de Termux mediante `GET /v1/agent/status`.

## 🛠 Configuración

### Configuración de Capacitor

Las aplicaciones móviles utilizan Capacitor para conectarse al servidor central. El archivo `capacitor.config.ts` debe configurarse correctamente:

```typescript
server: {
  androidScheme: 'https',
  url: 'https://tu-tunel-cloudflare.com', // Cambia esto por la URL de tu servidor
  cleartext: true
}
```

### Variables de Entorno

Las aplicaciones móviles utilizan las siguientes variables de entorno:

| Variable     | Descripción                                                       |
| ------------ | ----------------------------------------------------------------- |
| `SERVER_URL` | URL del servidor central (ej: `https://tu-tunel-cloudflare.com`). |
| `API_KEY`    | Clave de API para autenticación (opcional).                       |
| `DEBUG_MODE` | Modo de depuración (true/false).                                  |

## 📌 Notas Importantes

- **Seguridad**: Las aplicaciones deben configurarse para conectarse solo a servidores autorizados.
- **Uso legítimo**: Estas aplicaciones están diseñadas para auditoría y gestión de infraestructura propia.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Compilación**: Para compilar la APK, sigue las instrucciones en `[[BUILD_MOBILE.md]]` en el paquete de exportación.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura_General]]
- [[02_Proxy_FastAPI]]
- [[03_Nodo_Termux]]
- [[02_Configuracion/02_IP_Local_Celular]]

## 📌 Requisitos para el Uso

1. **App Maid**:
   - Android 8.0 o superior.
   - Conexión a Internet estable.
   - Permisos de red y notificaciones.

2. **APK AME**:
   - Android 9.0 o superior.
   - Permisos avanzados (acceso a almacenamiento, ubicación, etc.).
   - Configuración de Capacitor correcta en `capacitor.config.ts`.

## 📝 Ejemplo de Uso

1. **Configuración Inicial**:
   - Configura la URL del servidor en `capacitor.config.ts`.
   - Compila la APK siguiendo las instrucciones en `BUILD_MOBILE.md`.

2. **Interacción con Modelos**:
   - Abre la aplicación y selecciona un modelo de lenguaje.
   - Envía una consulta mediante la interfaz de chat.
   - Recibe la respuesta del modelo.

3. **Sincronización con el Agente de Termux**:
   - Consulta el estado del agente mediante la opción de estado.
   - Recibe comandos y actualizaciones del servidor.
