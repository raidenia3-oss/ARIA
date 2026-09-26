# 🔥 AURA ECOSYSTEM — Laboratorio de IA, Automatización y Seguridad Android

> **Unifica tres pilares esenciales:** Control de Versiones Profesional · Infraestructura de IA Local · Auditoría de Seguridad Móvil

---

## 📋 Tabla de Contenidos

1. [Arquitectura General](#arquitectura-general)
2. [Módulo 1: Git & Conventional Commits](#módulo-1-git--conventional-commits)
3. [Módulo 2: Infraestructura de IA Local](#módulo-2-infraestructura-de-ia-local)
4. [Módulo 3: Laboratorio de Seguridad Android](#módulo-3-laboratorio-de-seguridad-android)
5. [Puertos de Red](#puertos-de-red)
6. [Inicio Rápido](#inicio-rápido)
7. [Flujos de Trabajo Sugeridos](#flujos-de-trabajo-sugeridos)

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AURA ECOSYSTEM                               │
├─────────────────┬───────────────────┬──────────────────────────────┤
│  MÓDULO 1       │  MÓDULO 2         │  MÓDULO 3                    │
│  Git Profesional │  IA Local         │  Seguridad Android           │
│                 │                   │                              │
│  • .gitignore   │  • Ollama+Gemma 4 │  • MobSF (Docker)            │
│  • Conventional │  • LM Studio      │  • Frida                     │
│    Commits      │  • OpenRouter     │  • JADX                      │
│  • commit-      │  • Gemini API     │  • Drozer                    │
│    validator.py │  • Odysseus       │                              │
│                 │  • ComfyUI        │                              │
└─────────────────┴───────────────────┴──────────────────────────────┘
```

---

## Módulo 1: Git & Conventional Commits

### Estado Actual

- ✅ Repositorio Git inicializado en `feature/nodos-estables`
- ✅ Git config: `raidenia3-oss` / `raidenia3@gmail.com`
- ✅ `.gitignore` exhaustivo (300+ entradas)
- ✅ Script validador de commits

### Script de Validación de Commits

```bash
# Modo interactivo (asistente guiado)
.venv\Scripts\python.exe scripts\commit-validator.py

# Modo hook (valida automáticamente)
# Copiar a:
cp scripts/commit-validator.py .git/hooks/prepare-commit-msg
# En Windows:
copy scripts\commit-validator.py .git\hooks\prepare-commit-msg
```

### Formato Conventional Commits

```
feat(api): Agregar endpoint de autenticación
fix(core): Corregir null pointer en procesamiento
refactor(deploy): Simplificar pipeline de compilación
test(mobile): Agregar tests unitarios de conectividad
build(docker): Actualizar imagen de MobSF
chore(deps): Actualizar dependencias de Python
```

---

## Módulo 2: Infraestructura de IA Local

### Proveedores de IA

| Proveedor      | Tipo  | Costo                   | Endpoint                                           |
| -------------- | ----- | ----------------------- | -------------------------------------------------- |
| **OpenRouter** | Cloud | Gratuito (modelos free) | `https://openrouter.ai/api/v1`                     |
| **Gemini**     | Cloud | Gratuito (60 req/min)   | `https://generativelanguage.googleapis.com/v1beta` |
| **LM Studio**  | Local | 100% gratis             | `http://localhost:1234/v1`                         |
| **Ollama**     | Local | 100% gratis             | `http://localhost:11434`                           |

### Cadena de Fallback Automática

```
OpenRouter Free → Gemini → LM Studio → Proxy Legacy
```

Gestionado por `core/ai_config.py` + `core/proxy_chat_connector.py`

### Configuración Rápida de IA

```bash
# 1. Instalar Ollama (Windows: winget install Ollama.Ollama)
# 2. Descargar Gemma
ollama pull gemma3:4b

# 3. O usar el script automatizado
chmod +x scripts/setup-ai-models.sh
./scripts/setup-ai-models.sh

# 4. Configurar API keys en .env (ver más abajo)
```

### Docker Multi-Servicio

```bash
# Iniciar Odysseus + MobSF
docker compose up -d

# Iniciar también ComfyUI (diseño gráfico)
docker compose --profile design up -d

# Ver estado
docker compose ps
```

---

## Módulo 3: Laboratorio de Seguridad Android

### Herramientas Instalables

```bash
# Instalar todo el laboratorio
chmod +x scripts/install-security-tools.sh
./scripts/install-security-tools.sh

# O individualmente:
# Frida
pip install frida-tools

# JADX (descarga manual)
# https://github.com/skylot/jadx/releases

# Drozer
pip install drozer
```

### MobSF (Docker)

```bash
# Iniciar MobSF
docker compose up -d mobsf

# Acceder: http://localhost:8000
# Arrastrar y soltar APK para análisis estático/dinámico
```

### Guías Rápidas

**Frida:**

```bash
adb push frida-server /data/local/tmp/
adb shell chmod 755 /data/local/tmp/frida-server
adb shell /data/local/tmp/frida-server &
frida-ps -U
frida -U com.app -l hook.js
```

**JADX:**

```bash
./security-tools/jadx/bin/jadx-gui    # Interfaz gráfica
./security-tools/jadx/bin/jadx app.apk # CLI
```

**Drozer:**

```bash
adb forward tcp:31415 tcp:31415
drozer console connect
dz> run app.activity.info
dz> run scanner.provider.finduri
```

---

## Puertos de Red

| Servicio           | Puerto  | Descripción                             |
| ------------------ | ------- | --------------------------------------- |
| **AURA FastAPI**   | `5000`  | Backend principal del ecosistema        |
| **Odysseus (Web)** | `3000`  | Espacio agéntico de IA                  |
| **Odysseus (WS)**  | `3001`  | WebSocket para agentes                  |
| **MobSF**          | `8000`  | Análisis de seguridad Android           |
| **ComfyUI**        | `8188`  | Diseño gráfico con IA (perfil `design`) |
| **Ollama**         | `11434` | API de modelos locales                  |
| **LM Studio**      | `1234`  | API alternativa de modelos locales      |

---

## Inicio Rápido

### Variables de Entorno (`.env`)

Las variables críticas que requieres configurar:

```env
# === PROVEEDORES DE IA GRATUITOS ===
OPENROUTER_API_KEY=sk-or-v1-...   # https://openrouter.ai/keys
GEMINI_API_KEY=AIza...            # https://aistudio.google.com/apikey

# === PROVEEDORES LOCALES (ya preconfigurados) ===
LM_STUDIO_BASE_URL=http://localhost:1234/v1
```

### Pasos para Primera Ejecución

```bash
# 1. Inicializar Git (ya inicializado)
git status

# 2. Configurar API keys
#    Edita .env con tus claves de OpenRouter y Gemini

# 3. Instalar modelos locales
ollama pull gemma3:4b

# 4. Probar el sistema de IA
.venv\Scripts\python.exe -X utf8 test_all_providers.py

# 5. Iniciar backend
.venv\Scripts\python.exe -X utf8 -m uvicorn core.main:app --host 0.0.0.0 --port 5000 --reload

# 6. Desplegar APK en emulador
.venv\Scripts\python.exe -X utf8 core\deploy_pipeline.py

# 7. Iniciar servicios Docker (opcional)
docker compose up -d
```

---

## Flujos de Trabajo Sugeridos

### Desarrollo Diario

```bash
# 1. Pull + branch
git checkout -b feat/mi-funcionalidad

# 2. Hacer cambios y commit
.venv\Scripts\python.exe scripts\commit-validator.py
# ... sigue el asistente interactivo ...
git commit -F .git\COMMIT_EDITMSG

# 3. Push
git push origin feat/mi-funcionalidad
```

### Automatización con IA

```bash
# El router de IA elige automáticamente:
# 1. OpenRouter (si hay API key)
# 2. Gemini (fallback si OpenRouter falla)
# 3. LM Studio / Ollama (modo offline)
.venv\Scripts\python.exe -c "
from core.proxy_chat_connector import smart_chat_completion, ProxyChatMessage
import asyncio
msg = [ProxyChatMessage('user', 'Responde en una línea')]
resp = asyncio.run(smart_chat_completion(msg))
print(resp)
"
```

### Auditoría de Seguridad

```bash
# Pipeline completo en PC:
# 1. Compilar APK → instalar en emulador → arrancar backend
.venv\Scripts\python.exe -X utf8 core\deploy_pipeline.py

# 2. Analizar APK con MobSF
#    Arrastrar AURA-INSTALAME.apk a http://localhost:8000

# 3. Análisis dinámico con Frida + Drozer
frida -U com.ame.ecosystem -l hooks.js
drozer console connect
```

---

## 📁 Estructura de Archivos Clave

```
📁 AURA/
├── .env                          # Variables de entorno (API keys)
├── .gitignore                    # Ignorados globales
├── docker-compose.yml            # Odysseus + MobSF + ComfyUI
├── README.md                     # Este archivo
├── core/
│   ├── ai_config.py              # Config multi-proveedor
│   ├── proxy_chat_connector.py   # Router con fallback
│   ├── deploy_pipeline.py        # Pipeline de despliegue
│   └── main.py                   # Servidor FastAPI
├── scripts/
│   ├── commit-validator.py       # Conventional Commits
│   ├── setup-ai-models.sh        # Ollama + Gemma
│   ├── install-security-tools.sh # Frida + JADX + Drozer
│   └── ...
├── security-tools/               # Herramientas descargadas
└── docs/
    └── ai-local-setup.md         # Guía detallada de IA local
```

---

## 📊 Reporte del Ecosistema

```bash
# Verificar estado de todos los servicios
.venv\Scripts\python.exe -X utf8 -c "
from core.deploy_pipeline import EcosystemWatchdog
w = EcosystemWatchdog()
w.print_ecosystem_report(w.run_once())
"
```

---

## 🤝 Contribuciones

Este proyecto usa **Conventional Commits**. Por favor:

1. Usa `scripts/commit-validator.py` para crear commits válidos
2. Sigue el estándar: `tipo(alcance): Descripción en presente`
3. No hagas push directo a `main` — usa feature branches

---

## ⚖️ Licencia

**USO EDUCATIVO Y DE INVESTIGACIÓN ÚNICAMENTE.**

Las herramientas de seguridad aquí incluidas deben usarse exclusivamente en:

- Dispositivos propios
- Entornos de laboratorio autorizados
- Pruebas de penetración con permiso explícito

El mal uso de estas herramientas puede violar leyes locales e internacionales.

---

## 🚀 Comandos de Inicio - Backend y Task Worker

### Inicio Local (desarrollo)

```bash
# 1. Instalar dependencias completas
pip install -r requirements-full.txt
pip install playwright
python -m playwright install chromium

# 2. Iniciar servidor backend (Flask/FastAPI en puerto 5000)
python AME_Core/servidor_ame.py

# 3. En otra terminal: iniciar el worker de tareas de automatización
python -c "
import asyncio
from AURA_Core.automation_engine import get_engine
async def start():
    engine = await get_engine()
    print('Task Worker: AutomationEngine listo')
    print('Task Worker: Navegador headless inicializado')
asyncio.run(start())
"
```

### Inicio con PM2 (produccion local)

```bash
# Backend bajo PM2 con autoreinicio
pm2 start AME_Core/servidor_ame.py --name "AURA_BACKEND" --interpreter python
pm2 save

# Worker de tareas como segundo proceso
pm2 start python --name "AURA_TASK_WORKER" -- --c "from AURA_Core.automation_engine import get_engine; import asyncio; asyncio.run(get_engine().initialize()); print('Worker listo')"
pm2 save

# Ver ambos procesos
pm2 list
# Salida esperada:
# ┌────┬─────────────────┬──────────┬─────────┬──────────┐
# │ id │ name             │ mode     │ status  │ uptime   │
# ├────┼─────────────────┼──────────┼─────────┼──────────┤
# │ 0  │ AURA_BACKEND     │ fork     │ online  │ 3m       │
# │ 1  │ AURA_TASK_WORKER │ fork     │ online  │ 3m       │
# └────┴─────────────────┴──────────┴─────────┴──────────┘
```

### Inicio en Railway (produccion cloud)

El archivo `railway.toml` en la raiz del proyecto define automaticamente:

- **Build**: `requirements-full.txt` + Playwright + Chromium
- **Start**: `python AME_Core/servidor_ame.py`
- **Health**: `/api/status` (timeout 60s)
- **Restart**: ON_FAILURE

### Endpoints de tareas (API REST)

| Metodo | Ruta                     | Descripcion                                                                 |
| ------ | ------------------------ | --------------------------------------------------------------------------- |
| `POST` | `/api/automation/run`    | Encola una tarea de automatización (body: `{"task":"navigate","url":"..."}` |
| `GET`  | `/api/tasks`             | Lista todas las tareas (filtro: `?status=COMPLETED`)                        |
| `GET`  | `/api/tasks/<id>`        | Detalle de una tarea especifica                                             |
| `POST` | `/api/tasks/<id>/cancel` | Cancela una tarea pendiente                                                 |
| `WS`   | `/ws/tasks`              | WebSocket para updates en tiempo real                                       |

### Probar el pipeline completo

```bash
# Ejecutar la prueba de estres (verifica todo el pipeline)
python AURA_Core/test_stress_final.py

# Salida esperada:
#  REPORTE FINAL - PRUEBA DE ESTRES
#  [PASS] init_engine
#  [PASS] enqueue_task
#  [PASS] execute_task
#  [PASS] verify_completed
#  [PASS] api_tasks_verify
#  [PASS] websocket_validate
#  [PASS] websocket_broadcast
#  [PASS] cleanup
#  Total: 8 | [PASS] 8 | [FAIL] 0 | 100% exito
```
