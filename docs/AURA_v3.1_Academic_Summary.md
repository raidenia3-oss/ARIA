# AURA v3.1 - Resumen Académico

## Abstract

AURA (Autonomous Unified Reactive Architecture) es un sistema de inteligencia artificial distribuida que opera de forma autónoma, automejorable y autosustentable. A diferencia de los asistentes tradicionales, AURA no requiere intervención humana para mantenerse operativo: se auto-financia mediante un bot de micro-tareas, se auto-entrena mediante federated learning con knowledge distillation, y se despliega en múltiples dispositivos (PC, servidor cloud, móvil) como una única entidad coordinada.

Este documento resume la arquitectura, implementación y validación del sistema en su versión 3.1.

## 1. Introducción

### Problema
Los sistemas de IA actuales presentan limitaciones fundamentales:
- Requieren intervención humana constante para operación y mantenimiento
- Dependen de infraestructura pagada sin mecanismos de auto-sustentabilidad
- No mejoran automáticamente después del entrenamiento inicial
- Operan como silos aislados sin coordinación entre dispositivos

### Solución propuesta
AURA propone una arquitectura distribuida donde:
1. Múltiples dispositivos actúan como nodos de un único cerebro
2. Un orquestador asigna roles dinámicamente según disponibilidad
3. Un sistema de treasury invierte ganancias automáticamente en infraestructura
4. Un motor de entrenamiento federado mejora los modelos sin supervisión humana
5. Un dashboard en tiempo real provee observabilidad completa

## 2. Arquitectura

### 2.1 Visión general

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PC        │     │  Servidor   │     │  Celular    │
│  (Potente)  │     │  (Ligero)   │     │  (Externo)  │
│  Qwen 7B    │◄────►│  Qwen 0.5B  │◄────►│  APIs       │
│  Rol: POWER │     │  Rol: LIGHT │     │  Rol: EXT   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Backend    │
                    │  FastAPI    │
                    │  Orquestador│
                    └─────────────┘
```

### 2.2 Componentes principales

| Componente | Rol | Tecnología |
|------------|-----|------------|
| **Backend** | Orquestador central | FastAPI + Uvicorn |
| **Brain** | Estado unificado | SQLAlchemy + JSON |
| **Router** | Routing inteligente | Heurísticas + score |
| **Treasury** | Auto-financiamiento | Rollercoin API + presupuesto |
| **Trainer** | Auto-mejora | Knowledge Distillation |
| **Narrative** | Generación coherente | LLM + memoria + cliché detector |
| **Dashboard** | Observabilidad | Godot 4.6 + HTTPClient |

### 2.3 Protocolo de comunicación

```
Discovery:
  PC/Servidor → POST /api/orchestrator/register
  Backend     → 200 OK + role assignment

Chat:
  Client     → POST /api/chat
  Backend    → router inteligente → LLM → respuesta

Sync:
  PC         → POST /api/brain/sync
  Backend    → almacena + distribuye

Training:
  Server     → POST /api/brain/training/sync
  PC         → distillation → modelo mejorado
```

## 3. Implementación

### 3.1 Módulo 1: Persistent Brain

- **Archivo**: `backend/brain_orchestrator.py`
- **Función**: Estado unificado del sistema con memoria persistente
- **Almacenamiento**: SQLite + JSON files
- **Características**:
  - Registro de dispositivos con roles dinámicos
  - Historial de conversaciones
  - Sincronización de estado entre nodos

### 3.2 Módulo 2: Adaptive Routing

- **Archivo**: `backend/brain_router.py`
- **Función**: Enrutar consultas al mejor nodo disponible
- **Estrategia**:
  - Urgent → Servidor (baja latencia)
  - Quality → PC (modelo potente)
  - Fresh → API externa (diversidad)
  - Cache → offline buffer

### 3.3 Módulo 3: Treasury + Rollercoin

- **Archivo**: `backend/treasury_manager.py`
- **Función**: Administrar presupuesto y automatizar inversiones
- **Mecanismo**:
  - Rollercoin Bot genera ingresos 24/7
  - Treasury asigna daily budget: APIs, Hosting, Models, Reserve
  - Forecast 7 días con proyección financiera

### 3.4 Módulo 4: Federated Training

- **Archivo**: `backend/federated_training.py`
- **Función**: Mejora automática de modelos sin supervisión
- **Técnica**:
  - Knowledge Distillation: Teacher (PC) → Student (Server)
  - TrainingCheckpoint: Persistencia de épocas
  - ModelSync: Sincronización bidireccional
  - Auto-improve loop: cada 24h

### 3.5 Módulo 5: Dashboard Godot

- **Archivo**: `godot/scripts/dashboard/dashboard_manager.gd`
- **Función**: Visualización en tiempo real del sistema
- **Paneles**:
  - Brain Status, Routing, Treasury, Training
  - Rollercoin, Infrastructure, Console Log
  - Central Visualization (estilo JJK)
- **Actualización**: cada 2s vía HTTPClient

### 3.6 Módulo 6: E2E Testing

- **Backend**: `tests/test_e2e_backend.py` (7 tests)
- **Godot**: `godot/scripts/dashboard/test_e2e.gd` (8 tests)
- **Cobertura**: health, brain, routing, treasury, training, rollercoin, chat, dashboard

### 3.7 Módulo 7: Narrative Engine

- **Archivo**: `backend/narrative_engine.py`
- **Función**: Generar historias coherentes sin clichés
- **Componentes**:
  - NarrativeMemory: nunca olvida personajes/trama
  - ClichéDetector: regex patterns + score
  - ConsistencyChecker: valida acciones de personajes
  - ToneAnalyzer: system prompts por tono
- **Endpoints**: `/api/narrative/stories/*`

## 4. Resultados

### 4.1 Validación técnica

| Test Suite | Resultado |
|------------|-----------|
| Backend E2E | 7/7 PASS |
| Integration API | 9/9 PASS |
| Godot project | OK |
| Android APK | 26.3 MB exportado |

### 4.2 Métricas de performance

| Métrica | Valor |
|---------|-------|
| Tiempo de respuesta API | < 200ms |
| Actualización dashboard | 2s |
| Tamaño APK | 26.3 MB |
| Modelo local | Qwen 0.5B |
| Dispositivos soportados | 3 |

### 4.3 Estado del sistema

```
✅ Backend FastAPI operativo
✅ 15+ endpoints activos
✅ Dashboard 9 paneles funcional
✅ APK Android compilado
✅ Narrative Engine operativo
✅ 16/16 tests passing
```

## 5. Deployment

### Opción A: PythonAnywhere (recomendado para demo)
- Gratis, HTTPS automático
- WSGI config con `application = app`
- Keep-alive cada 4 minutos

### Opción B: Oracle Cloud Always Free
- 2 vCPU + 12GB RAM
- Ubuntu 22.04
- Systemd service para 24/7

### Opción C: Fly.io (infraestructura existente)
- Ya configurado en proyecto
- $0-3/mes

## 6. Trabajo futuro

1. **Escalabilidad**: migrar a Kubernetes para orquestación avanzada
2. **Modelos**: incorporar LLMs locales más grandes (Qwen 7B, Llama 3)
3. **Seguridad**: agregar JWT + rate limiting avanzado
4. **Monitoreo**: Grafana + Prometheus + alertas Discord
5. **Mobile**: app nativa Android con Godot + Godot Engine

## 7. Conclusión

AURA demuestra que es posible construir un sistema de IA verdaderamente autónomo: se financia solo, se mejora solo, y se mantiene operativo sin intervención humana. La arquitectura distribuida permite tolerancia a fallos y escalabilidad, mientras que el motor narrativo muestra capacidades avanzadas de generación de lenguaje coherente.

Este proyecto sirve como prueba de concepto para sistemas de IA autosuficientes del futuro.

---

**Palabras clave**: IA distribuida, auto-mejora, federated learning, orquestación, autonomía.
