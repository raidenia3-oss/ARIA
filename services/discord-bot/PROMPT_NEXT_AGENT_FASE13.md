# Prompt para Cline: Fase 13 - WiFi Radar / Sensing (Monitoreo Ambiental WiFi)

## Contexto
Fases 1-12 completadas. El usuario quiere una nueva capacidad que use WiFi como radar para mapear espacios físicos y monitorear actividad en la casa/entorno. Esto se basa en que las señales WiFi (RSSI, CSI, etc.) pueden usarse para detectar presencia, movimiento, y hasta formas de cuerpo sin cámaras.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Backend: `ame_backend/` (FastAPI, Python 3.11)
- Frontend: `frontend/` (Next.js 15)
- Hardware: cualquier laptop con WiFi (sin hardware especial)

## Tareas

### 1. Backend: WiFi Sensor Service
- Crear `ame_backend/src/tools/wifi_radar.py`:
  - Clase `WiFiRadar` que escanee redes WiFi cercanas usando `scapy` o `netsh` (Windows) / `nmcli` (Linux)
  - Obtener RSSI (señal) de cada red visible
  - Mapear señales a "blobs" de presencia (cuánto más fuerte la señal, más cerca está la fuente)
  - Detectar cambios en el tiempo para identificar movimiento
  - Generar mapa de calor 2D simple basado en intensidad de señal
  - Exportar datos en formato JSON para frontend

### 2. Backend: WiFi Sensing API
- En `ame_backend/src/main.py`, agregar endpoints:
  - `GET /api/wifi/scan` — escanea redes WiFi y devuelve lista con SSID, BSSID, RSSI, canal, frecuencia
  - `GET /api/wifi/presence-map` — devuelve mapa de calor de presencia basado en RSSI
  - `GET /api/wifi/stream` — SSE stream que emite actualizaciones de señal cada 1s
  - `POST /api/wifi/calibrate` — permite al usuario marcar puntos de referencia (nombre + ubicación) para calibrar el mapa

### 3. Backend: Detección de Actividad
- En `ame_backend/src/tools/wifi_radar.py`:
  - `detect_motion()` — compara escaneos consecutivos, detecta variaciones significativas de RSSI
  - `detect_presence_zones()` — agrupa redes por intensidad para inferir zonas ocupadas
  - `predict_location()` — estima ubicación más probable basada en triangulación de señales
  - `detect_anomalies()` — detecta redes nuevas o desaparecidas (posible intruso o cambio en el entorno)

### 4. Frontend: WiFi Radar UI
- Crear `frontend/app/wifi-radar/page.tsx`:
  - Canvas 2D/Three.js para mostrar mapa de calor de señales WiFi
  - Puntos de acceso como círculos con intensidad proporcional a RSSI
  - Líneas de conexión entre nodos
  - Indicador de movimiento: cuando detecta cambios, muestra animación de "ondas"
  - Panel de lista de redes detectadas con SSID, RSSI, canal
  - Botón para calibrar (marcar puntos en el mapa)
  - Historial de actividad (timeline de movimiento)

### 5. Integración con Gestos
- En `frontend/app/wifi-radar/page.tsx`:
  - Gestos para controlar el radar:
    - `open_hand` → activar/desactivar escaneo continuo
    - `fist` → detener escaneo
    - `index` → seleccionar red en el mapa
    - `swipe` → cambiar vista (mapa de calor / lista / timeline)
  - Mostrar gesto detectado en el overlay del radar

### 6. Integración con Sistema de Alarmas
- En `training/scripts/alerts.py`, agregar checks:
  - Si aparece una red desconocida con RSSI alto → alerta "Posible dispositivo desconocido"
  - Si RSSI de una red cambia más de 20dB en 10s → alerta "Movimiento detectado"
  - Si todas las señales desaparecen → alerta "Posible interferencia o apagado de routers"
- En `ame_backend/src/observability.py`, registrar métricas de WiFi:
  - Cantidad de redes detectadas
  - RSSI promedio
  - Variabilidad de señal
  - Zonas activas

## Reglas
- NO modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`
- NO uses librerías que requieran root/privilegios especiales en Windows sin advertir
- Si `scapy` no está disponible, usar `netsh wlan show networks mode=bssid` en Windows como fallback
- Usa `logging` en lugar de `print()`
- Mantén compatibilidad con endpoints existentes

## Entregables
1. `ame_backend/src/tools/wifi_radar.py`
2. Modificaciones en `ame_backend/src/main.py` con endpoints WiFi
3. `frontend/app/wifi-radar/page.tsx`
4. Integración en `training/scripts/alerts.py`
5. Integración en `ame_backend/src/observability.py`

## Validación final
1. Backend compila
2. Frontend typecheck
3. Backend arranca
4. Probar `/api/wifi/scan` desde navegador o curl
5. Abrir `/wifi-radar` y verificar mapa de calor
6. Probar detección de movimiento moviendo el router/ dispositivo
