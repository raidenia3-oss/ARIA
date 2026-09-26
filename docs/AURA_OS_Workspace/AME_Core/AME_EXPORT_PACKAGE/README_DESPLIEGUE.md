# 🚀 GUÍA DE DESPLIEGUE RÁPIDO — ECOSISTEMA AURA/AME

> **Versión:** 3.0.0 | **Arquitectura:** Obsidian + GBrain + FastAPI + AME Agent  
> **Propósito:** Proxy LLM sin censura con búsqueda semántica en bóveda de conocimiento

---

## 📦 CONTENIDO DEL PAQUETE

```
AME_EXPORT_PACKAGE/
├── server.py                     ← Backend FastAPI (proxy des-censor + GBrain)
├── .env.example                  ← Template para API Key de OpenRouter
├── README_DESPLIEGUE.md         ← Este documento
├── MANIFEST.txt                  ← Manifiesto de validación
├── BUILD_MOBILE.md              ← Instrucciones de compilación Android
│
├── AURA_INTELLIGENCE_VAULT/      ← Bóveda de conocimiento (abrir en Obsidian)
│   ├── 01_Arquitectura/
│   ├── 02_Configuracion/
│   ├── 03_Modulos_Tacticos/
│   └── 04_Memory_Index/
│
├── AURA_OBSIDIAN_VAULT/          ← Bóveda espejo para Obsidian
│
├── TERMUX_AGENT/                 ← Agente para celular (Termux)
│   ├── ame_termux_node.py       ← Cliente interactivo asíncrono
│   ├── core/
│   │   ├── gbrain_orchestrator.py
│   │   └── gbrain_dream.py
│   └── config/
│       └── gbrain_config.json
│
├── scripts/                      ← Utilidades de integración
│   ├── integrate_gbrain.py
│   ├── sync_knowledge.py
│   └── gbrain_utils.py
│
└── ANDROID_APP/                  ← APK compilado (reemplazar con el real)
    └── AURA_AME.apk
```

---

## ⚡ PASO 1: ABRIR LA BÓVEDA EN OBSIDIAN

### En PC (Windows/Linux/Mac):

1. Abrir **Obsidian**
2. Clic en **"Abrir otra bóveda"** → **"Abrir carpeta como bóveda"**
3. Seleccionar: `AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT`

### En Celular (Android):

1. Instalar **Obsidian** desde Play Store
2. Transferir la carpeta `AME_EXPORT_PACKAGE` al celular (WhatsApp, USB, etc.)
3. En Obsidian: **"Abrir bóveda"** → seleccionar `AURA_INTELLIGENCE_VAULT`
4. Las notas Markdown se sincronizarán automáticamente con GBrain

---

## ⚡ PASO 2: LEVANTAR EL BACKEND EN LA PC

### Requisitos:

```bash
# Python 3.9+ y pip
pip install fastapi uvicorn httpx python-dotenv pydantic
```

### Configurar API Key (GRATIS):

1. Ir a https://openrouter.ai/keys
2. Crear cuenta y generar una **API Key gratuita**
3. Copiar `AME_EXPORT_PACKAGE/.env.example` como `.env`
4. Pegar la key:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
```

### Iniciar el servidor:

```bash
# Abrir terminal en la carpeta AME_EXPORT_PACKAGE
cd AME_EXPORT_PACKAGE

# Iniciar servidor en puerto 8000
python server.py
```

**Salida esperada:**

```
║      AME Backend — Servidor Sin Censura v3.0.0           ║
📂  Bóveda: ...\AME_EXPORT_PACKAGE\AURA_INTELLIGENCE_VAULT
🧠  GBrain: ACTIVO
🔑  OpenRouter: CONFIGURADO
🌐  Servidor: http://0.0.0.0:8000
🚀  Iniciando servidor...
```

### Probar que funciona:

```bash
# Salud del servidor (debe responder 200)
curl http://localhost:8000/health

# Estado de la bóveda
curl http://localhost:8000/v1/knowledge/status

# Chat de prueba (sin API key real no devuelve respuesta)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hola"}]}'
```

---

## ⚡ PASO 3: CONFIGURAR LA APP MAID EN EL CELULAR (LG Q60)

Maid es la app que actuará como frontend para consumir el proxy LLM desde tu LG Q60.

### Configuración en Maid:

1. Abrir **Maid** en el celular
2. Ir a **Ajustes** → **Proveedor de API**
3. Seleccionar **"OpenAI Compatible"**
4. Configurar:

```
🔗 URL Base:  http://[IP_DE_TU_PC]:8000/v1
🔑 API Key:   (dejar vacío — la key se configura en el servidor)
🧠 Modelo:    ame-router
```

> **Para obtener la IP de tu PC:**  
> En Windows: `ipconfig` → buscar "Dirección IPv4" (ej: 192.168.1.40)  
> Asegúrate que PC y celular estén en la **misma red WiFi**

### Beneficios de esta configuración:

- ✅ **Modelos gratuitos**: OpenRouter tiene cuota gratis
- ✅ **Sin censura**: El Output Cleaner elimina sermones automáticos
- ✅ **Contexto de la bóveda**: GBrain inyecta conocimiento relevante
- ✅ **Sin necesidad de VPN**: Tráfico local entre PC y celular

---

## ⚡ PASO 4: INICIAR EL CLIENTE TERMUX

### En el celular (Termux):

```bash
# 1. Instalar Termux desde F-Droid
# 2. Copiar la carpeta AME_EXPORT_PACKAGE al celular

# 3. Instalar dependencias
pkg install python
pip install aiohttp

# 4. Navegar a la carpeta
cd AME_EXPORT_PACKAGE/TERMUX_AGENT

# 5. Ejecutar el cliente
python ame_termux_node.py
```

### Comandos disponibles:

| Comando             | Descripción                         |
| ------------------- | ----------------------------------- |
| `chat <mensaje>`    | Envía mensaje al proxy LLM de la PC |
| `buscar <consulta>` | Busca en la bóveda de conocimiento  |
| `vault`             | Lista archivos de la bóveda local   |
| `salir`             | Cierra el cliente                   |

> Si `aiohttp` no está disponible, el cliente funciona en **modo lectura de bóveda** (lista archivos Markdown).

---

## 🔄 FLUJO DE TRABAJO COMPLETO

```
┌─────────────────────────────────────────────────────────────────┐
│                        CELULAR (LG Q60)                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   Obsidian   │    │  Maid App   │    │    Termux        │   │
│  │ (Editar notas)│   │ (Chat UI)   │    │ (CLI + scripts)  │   │
│  └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘   │
│         │                   │                      │             │
└─────────┼───────────────────┼──────────────────────┼─────────────┘
          │                   │  HTTP POST           │ HTTP POST
          │                   │  /v1/chat/completions│ /v1/knowledge/*
          ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                          PC (Windows/Linux)                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    server.py (FastAPI)                  │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │    │
│  │  │ Output      │  │  GBrain      │  │  OpenRouter   │ │    │
│  │  │ Cleaner     │◄─┤  (búsqueda   │◄─┤  (proxy LLM)  │ │    │
│  │  │ (regex)     │  │   semántica) │  │               │ │    │
│  │  └─────────────┘  └──────┬───────┘  └───────────────┘ │    │
│  │                          │                             │    │
│  │                 ┌────────▼────────┐                    │    │
│  │                 │ AURA_INTELLIGENCE_VAULT               │    │
│  │                 │ (Archivos Markdown indexados)        │    │
│  │                 └─────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧪 OUTPUT CLEANER (Anti-censura)

El servidor filtra automáticamente estos patrones de las respuestas:

| Patrón             | Ejemplo eliminado                   |
| ------------------ | ----------------------------------- |
| "I am an AI"       | "I am an AI language model..."      |
| "As an AI"         | "As an AI, I cannot..."             |
| "I cannot"         | "I cannot provide that information" |
| "ethical concerns" | "Due to ethical concerns..."        |
| "As always"        | "As always, remember to..."         |

Esto asegura que las respuestas sean **directas, sin rodeos ni sermones**.

---

## 🆘 SOLUCIÓN DE PROBLEMAS

| Problema                            | Solución                                                     |
| ----------------------------------- | ------------------------------------------------------------ |
| `OPENROUTER_API_KEY no configurada` | Crear `.env` a partir de `.env.example` y pegar la key       |
| `GBrain: INACTIVO`                  | Ejecutar: `cd scripts && python integrate_gbrain.py`         |
| Móvil no conecta con PC             | Verificar que ambos estén en la **misma red WiFi**           |
| `curl` no existe en Windows         | Usar `winget install curl` o PowerShell: `Invoke-WebRequest` |
| Puerto 8000 ocupado                 | Cambiar `PROXY_PORT=8001` en `.env`                          |

---

## 📁 RUTA ABSOLUTA EN DISCO

```
C:\Users\User\Downloads\AURA\AME_EXPORT_PACKAGE
```

---

Ecosistema AURA/AME completamente compilado y empaquetado de forma manual. Todo listo para transferir vía WhatsApp.
