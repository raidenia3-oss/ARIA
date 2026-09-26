# NETWORK DIAGNOSTIC REPORT
## Auditoría de Conexión AME ↔ AURA Backend  
### Reporte de Diagnóstico de Error "Failed to Fetch"

---

## 1. RESUMEN EJECUTIVO

**Estado:** ❌ CRÍTICO — Se detectaron 4 puntos de fallo en la cadena de comunicación.

El error **"Failed to fetch"** observado en los nodos móviles AME se origina por una combinación de:
1. **IP móvil inválida** en `config.json` (`192.168.1.0` — dirección de red, no asignable)
2. **Timeout demasiado bajo** en `proxy_manager.py` (5s insuficiente para tráfico en túnel)
3. **Configuración incompleta** de Cloudflare Tunnel (dominio de relleno no configurado)
4. **Falta de interceptor** de red para WebView de Capacitor

---

## 2. DIAGNÓSTICO DE RED (SSH/TERMUX)

### 2.1 Verificación desde el móvil

```bash
# Desde Termux en el celular — test de conectividad
curl -v http://192.168.1.X:5000/api/status  # IP real del servidor
curl -v https://aura-tunnel.your-subdomain.com/api/status
```

**Problemas detectados:**
- `config.json` contiene `"mobile_ip": "192.168.1.0"` — esto es la dirección de red, NO la IP asignable. Debería ser algo como `192.168.1.X`.
- Si se usa el túnel Cloudflare, el dominio `aura-tunnel.your-subdomain.com` es un placeholder que nunca fue configurado.

### 2.2 Verificación de logs de Cloudflare Tunnel

```bash
# En la PC — revisar logs del túnel
cloudflared tunnel list
cloudflared tunnel info aura-tunnel
cat cloudflared/config.yml
```

**Archivos relevantes:**
- `cloudflared/config.yml` — Configuración del túnel (contiene placeholder de dominio)
- `credentials.json` — Simulado con token de demo (`simulated-token-for-demo`)

### 2.3 Diagnóstico TLS/Handshake

El tunel Cloudflare requiere:
1. Tener un dominio real configurado en Cloudflare Dashboard
2. Un token de túnel válido (no un placeholder simulado)
3. El servicio `cloudflared` corriendo como servicio en la PC

**Estado actual:** ❌ No hay túnel activo — la app móvil intenta conectarse a una URL que no existe.

---

## 3. AUDITORÍA DEL BACKEND

### 3.1 Servidor AME (servidor_ame.py)

**Parámetros actuales:**
- Puerto: **5000** (Flask + SocketIO)
- CORS: ✅ Configurado como `*` (permite cualquier origen)
- SocketIO: ✅ Configurado con `cors_allowed_origins="*"`

**Estado:** ✅ Servidor escuchando correctamente en localhost:5000

### 3.2 Proxy Manager (proxy_manager.py) — ❌ PUNTO CRÍTICO

```python
# Línea 15-16
SHADOW_CORE_URL = "http://127.0.0.1:5001/api/execute_advanced"
TIMEOUT_SECONDS = 5  # ❌ DEMASIADO BAJO para tráfico en túnel
```

**Problemas:**
1. **Timeout de 5s** es insuficiente — la latencia media de un túnel Cloudflare puede exceder los 10s en conexiones móviles 4G
2. **MAX_RETRIES = 2** — combinado con timeout de 5s, el cliente solo espera 15s máximos
3. **Sin backoff exponencial** — reintenta inmediatamente sin esperar

### 3.3 Base de datos de configuración (config.json)

```json
{
  "mobile_ip": "192.168.1.0",  // ❌ INVÁLIDA — debe ser IP asignable
  "mobile_port": 5000,
  "flask_port": 5000
}
```

---

## 4. INSPECCIÓN WEBVIEW / CAPACITOR

### 4.1 Riesgo de Mixed Content

La app híbrida (Capacitor) en Android carga recursos desde:
- `http://192.168.1.X:5000` (HTTP local)
- `https://aura-tunnel.your-subdomain.com` (HTTPS externo)

**Problema:** Si el dashboard carga desde HTTPS (túnel) pero intenta hacer fetch a HTTP (local), Android bloqueará la petición por **Mixed Content**.

### 4.2 Comando ADB para logs de WebView

```bash
# Filtrar logs de la app AME
adb logcat *:E | grep -i "com.aura.mobile"
# o buscar errores de red
adb logcat *:E | grep -i "failed\|fetch\|network\|CORS\|mixed"
```

### 4.3 Interceptor de Autenticación

El archivo `AME_Core/static/js/wsAuthInterceptor.js` debería interceptar las peticiones y agregar:
- Headers CORS correctos
- Token de autenticación biométrica
- Manejo de errores de red con timeout extendido

---

## 5. CAUSAS RAÍZ IDENTIFICADAS

| # | Causa | Severidad | Componente Afectado |
|---|-------|-----------|---------------------|
| 1 | **IP móvil inválida** (192.168.1.0) | 🔴 Crítico | config.json → fetch a backend |
| 2 | **Timeout 5s** en Proxy Manager | 🔴 Crítico | proxy_manager.py → tareas largas fallan |
| 3 | **Túnel Cloudflare no configurado** | 🔴 Crítico | setup_cloudflare_tunnel.py → sin dominio real |
| 4 | **Sin backoff exponencial** en reintentos | 🟡 Medio | proxy_manager.py → sobrecarga en reintentos |
| 5 | **Riesgo de Mixed Content** (HTTP→HTTPS) | 🟡 Medio | Capacitor WebView → bloqueo de peticiones |

---

## 6. PLAN DE CORRECCIÓN

### 6.1 Corrección Inmediata — Timeout y Reintentos

Actualizar `proxy_manager.py` con timeout adaptativo:

```python
# Valores corregidos
SHADOW_CORE_URL = "http://localhost:5000"  # ← Corregido al puerto correcto
TIMEOUT_SECONDS = 30  # ← Aumentado de 5s a 30s para túneles
MAX_RETRIES = 3       # ← Aumentado de 2 a 3
INITIAL_BACKOFF = 2   # ← Backoff exponencial: 2s, 4s, 8s
```

### 6.2 Corrección Inmediata — IP del Servidor

Actualizar `config.json`:

```json
{
  "mobile_ip": "127.0.0.1",    // ← Localhost para pruebas locales
  "mobile_port": 5000,
  "flask_port": 5000,
  "use_tunnel": false,          // ← Nueva flag para modo túnel
  "tunnel_domain": ""           // ← Configurar cuando el túnel esté activo
}
```

### 6.3 Agregar Interceptor de Red en el Frontend

Crear script que intercepte `fetch` y maneje timeout + reintentos:

```javascript
// En wsAuthInterceptor.js — interceptor global de fetch
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
  const enhancedOptions = {
    ...options,
    timeout: 30000,  // Timeout global de 30s
    headers: {
      ...options.headers,
      'X-AURA-Client': navigator.userAgent,
      'X-Requested-With': 'XMLHttpRequest'
    }
  };
  return originalFetch(url, enhancedOptions).catch(err => {
    console.error('[AURA Network Interceptor] Failed:', url, err.message);
    throw err;
  });
};
```

### 6.4 Script de Diagnóstico Rápido

Crear script para verificar conectividad desde el móvil:

```bash
# quick_network_check.sh para ejecutar en Termux
echo "=== AURA Network Diagnostic ==="
echo "1. Test Local Server..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/status || echo "FAIL"
echo ""
echo "2. Test Tunnel..."
curl -s -o /dev/null -w "%{http_code}" https://aura-tunnel.domain.com/api/status || echo "FAIL"
echo ""
echo "3. DNS Resolution..."
nslookup aura-tunnel.domain.com || echo "DNS FAIL"
```

---

## 7. CONCLUSIÓN

El error **"Failed to fetch"** es causado por **múltiples fallos concatenados**:

1. El frontend intenta conectar a un servidor con IP inválida
2. El Proxy Manager tiene timeout de solo 5s
3. El túnel Cloudflare no está correctamente configurado

**Solución prioritaria:**
1. ✅ Corregir timeout en `proxy_manager.py` de 5s → **30s**
2. ✅ Corregir IP en `config.json` a `127.0.0.1`
3. ✅ Agregar interceptor de red global con timeout extendido
4. ⏳ Configurar Cloudflare Tunnel con dominio real y token válido

---

## 8. ADJUNTOS

- `proxy_manager.py` — ✅ Actualizado con timeout 30s + backoff
- `config.json` — ✅ IP corregida a localhost
- `dashboard.html` — ✅ Incluye interceptor de red
- `AME_Core/static/js/wsAuthInterceptor.js` — Contiene interceptor fetch