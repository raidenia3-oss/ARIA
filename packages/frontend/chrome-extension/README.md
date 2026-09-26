# AURA OS Chrome Extension

Extensión oficial de Chrome para integrar AURA OS con el navegador del usuario.

## Permisos solicitados

| Permiso | Uso |
|---------|-----|
| `activeTab` | Leer información de la pestaña activa |
| `scripting` | Ejecutar scripts en pestañas autorizadas |
| `storage` | Guardar configuración local (deviceId, sitios permitidos) |
| `alarms` | Keepalive del service worker |
| `host_permissions` | `http://localhost:8000/` (comunicación con AURA) y `https://*/*` (solo en sitios autorizados) |

## Instalación

1. Abrir Chrome y navegar a `chrome://extensions/`
2. Activar "Modo desarrollador"
3. Hacer clic en "Cargar extensión sin empaquetar"
4. Seleccionar `frontend/chrome-extension/`

## Configuración

- **Activar/Desactivar**: Botón en el popup de la extensión
- **Sitios permitidos**: Página de opciones (`options.html`) — añadir URLs una por línea
- **Autenticación**: El `deviceId` se genera automáticamente y se guarda en `chrome.storage.local`

## Comunicación con AURA

- **WebSocket**: Conexión bidireccional con `ws://localhost:8000/api/mobile/sync/chrome-ext`
- **Autenticación**: Primer mensaje `{ type: "auth", token: "..." }`
- **Reconexión**: Retry fijo cada 5s si AURA está offline (backoff exponencial pendiente)
- **Sin duplicados**: El backend echoa el `commandId` de vuelta como `eventId` en la respuesta. La extensión procesa comandos secuencialmente (variable `currentAction`) y descarta comandos nuevos si hay uno activo.

## Herramientas disponibles

| Tool | Descripción |
|------|-------------|
| `browser.extension_status` | Estado de conexión, deviceId, sitios permitidos |
| `browser.active_tab` | Pestaña activa (tabId, url, title) |
| `browser.read_visible` | Texto visible de la pestaña (primeros 5000 chars) |
| `browser.open_url` | Abre URL en Chrome (solo si está autorizada) |
| `browser.click` | Click en selector CSS |
| `browser.type` | Escribe texto en campo |
| `browser.select` | Selecciona opción en `<select>` |
| `browser.screenshot` | Captura de pantalla de la pestaña |
| `browser.stop` | Detiene tarea activa |

## Seguridad

- **Nunca** se extraen contraseñas, cookies, tokens ni claves bancarias
- Las interacciones son **solo con contenido visible** en pestañas autorizadas
- Los comandos provienen del backend local (localhost:8000)
- URLs sanitizadas en logs (se eliminan query params y fragmentos)
- Las credenciales del bot se guardan en `.env` local, nunca en el repo
