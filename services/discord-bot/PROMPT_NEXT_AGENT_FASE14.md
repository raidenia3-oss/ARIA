# Prompt para Cline: Fase 14 - Predicción de Terremotos y Monitoreo Sísmico

## Contexto
Fases 1-13 completadas. Usuario solicita integrar capacidades de predicción/monitoreo de terremotos, especialmente tras el evento sísmico en Colombia. La idea es usar datos sísmicos públicos, análisis de patrones locales y correlación con otros sensores (WiFi, vibración) para generar alertas tempranas.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Backend: `ame_backend/` (FastAPI, Python 3.11)
- Frontend: `frontend/` (Next.js 15)
- APIs públicas: USGS Earthquake Hazards Program, EMSC, IRIS (sin API key requerida)
- Hardware: micrófono (detectar vibraciones低频), acelerómetro (si existe), WiFi sensing (Fase 13)

## Tareas

### 1. Backend: Servicio Sísmico
- Crear `ame_backend/src/tools/earthquake_monitor.py`:
  - Clase `EarthquakeMonitor` que:
    - Consuma feeds públicos de terremotos en tiempo real (USGS GeoJSON feed: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson)
    - Consuma histórico de terremotos de la región del usuario (por defecto Colombia, configurable)
    - Almacene eventos en SQLite local (`data/earthquakes.db`) para análisis offline
    - Detecte patrones: enjambres sísmicos, incremento de magnitud, patrones temporales
    - Calcule "risk score" basado en:
      - Cantidad de eventos en últimas 24h/7d
      - Tendencia de magnitud
      - Distancia a puntos de interés del usuario
      - Profundidad promedio

### 2. Backend: API de Terremotos
- En `ame_backend/src/main.py`, agregar endpoints:
  - `GET /api/earthquakes/recent` — últimos terremotos mundiales (desde USGS)
  - `GET /api/earthquakes/nearby` — terremotos cercanos a ubicación del usuario (lat, lon, radius_km)
  - `GET /api/earthquakes/history` — histórico de la región
  - `GET /api/earthquakes/risk` — cálculo de riesgo actual
  - `GET /api/earthquakes/stream` — SSE stream que actualiza cuando hay nuevos eventos
  - `POST /api/earthquakes/alert` — configura alertas personalizadas (magnitud mínima, radio)

### 3. Backend: Detección Local (Opcional pero Innovador)
- En `ame_backend/src/tools/earthquake_monitor.py`:
  - Usar micrófono del dispositivo para detectar sonidos de baja frecuencia (<20Hz) que pueden preceder a terremotos
  - O usar acelerómetro si está disponible (líneas de comando o API nativa)
  - Correlacionar detecciones locales con eventos remotos para mejorar precisión
  - Generar "local anomaly score"

### 4. Backend: Motor de Predicción Simple
- En `ame_backend/src/tools/earthquake_forecaster.py`:
  - Modelo estadístico simple (NO deep learning complejo):
    - Análisis de frecuencia de eventos (Poisson process)
    - Detección de enjambres (clustering temporal)
    - Patrones Gutenberg-Richter básicos
    - Correlación con datos WiFi sensing (si hay)
  - Entrenar/ajustar con datos históricos de USGS para región Colombia/Latam
  - Exportar predicciones como JSON con:
    - `probability`: 0-1
    - `time_window`: horas/días
    - `magnitude_range`: [min, max]
    - `confidence`: 0-1
    - `factors`: lista de factores considerados

### 5. Frontend: Mapa Sísmico
- Crear `frontend/app/earthquakes/page.tsx`:
  - Mapa mundial con Leaflet o Mapbox GL JS (gratis) mostrando:
    - Terremotos recientes como círculos con tamaño = magnitud, color = profundidad
    - Zona del usuario marcada
    - Radio de alerta configurable
  - Timeline de eventos recientes
  - Panel de riesgo actual con score y factores
  - Alertas configurables (magnitud mínima, radio)
  - Modo "Predicción" que muestra zonas de riesgo calculadas

### 6. Integración con Alertas Existentes
- En `training/scripts/alerts.py`:
  - Si `risk_score > umbral` → alerta
  - Si hay terremoto cercano detectado → alerta inmediata
  - Si predicción indica probabilidad alta → alerta preventiva
- En `ame_backend/src/main.py`:
  - Endpoint `/api/alerts` puede incluir alertas sísmicas

### 7. Integración con WiFi Radar (Fase 13)
- En `ame_backend/src/tools/earthquake_monitor.py`:
  - Si hay datos de WiFi sensing disponibles, buscar correlaciones:
    - Cambios abruptos en RSSI justo antes de un evento sísmico
    - Patrones de interferencia inusuales
  - Usar como señal adicional en el modelo de predicción

## Reglas
- NO modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`
- NO uses APIs que requieran pago o keys para datos básicos (USGS/EMSC son gratuitos)
- NO hagas predicciones deterministas; SIEMPRE expresa incertidumbre
- Usa `logging` en lugar de `print()`
- Mantén compatibilidad con endpoints existentes
- Almacena datos localmente para funcionamiento offline

## Entregables
1. `ame_backend/src/tools/earthquake_monitor.py`
2. `ame_backend/src/tools/earthquake_forecaster.py`
3. Modificaciones en `ame_backend/src/main.py` con endpoints sísmicos
4. `frontend/app/earthquakes/page.tsx`
5. Integración en `training/scripts/alerts.py`
6. Integración en `ame_backend/src/observability.py`

## Validación final
1. Backend compila
2. Frontend typecheck
3. Backend arranca
4. Probar `/api/earthquakes/recent` — debe devolver eventos reales de USGS
5. Probar `/api/earthquakes/risk` — debe calcular risk score
6. Abrir `/earthquakes` en navegador, verificar mapa y timeline
7. Verificar que alertas se generan en `alerts.jsonl` cuando hay eventos cercanos
