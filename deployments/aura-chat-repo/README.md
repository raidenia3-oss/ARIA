---
title: AURA Chat
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# 🤖 AURA Chat

Asistente IA autónomo 24/7. Frontend Gradio público conectado al backend AURA para routing multi-modelo (Gemini, Groq, OpenRouter, HF, Ollama), memoria semántica, búsqueda web en vivo y tool calling.

[![Hugging Face Space](https://img.shields.io/badge/🤗-Hugging%20Face%20Space-blue)](https://huggingface.co/spaces/raiden456/aura-chat)
[![GitHub](https://img.shields.io/badge/GitHub-raidenia3--oss/AURA--server.01-181717?logo=github)](https://github.com/raidenia3-oss/AURA-server.01)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Características

- **Frontend Gradio**: interfaz pública 24/7 en Hugging Face Spaces
- **Backend AURA**: routing multi-modelo, memoria semántica RAG, búsqueda web autónoma
- **Configuración dinámica**: system prompt, temperatura y máx. tokens ajustables
- **Health check**: endpoint `/health` para ping 24/7
- **Memoria conversacional**: últimos 10 mensajes como contexto
- **Caché LRU**: respuestas repetidas no consumen créditos extra
- **Logging rotado**: interacciones limitadas a 5MB para no saturar el Space

## 📊 Estado del sistema

El Space muestra en vivo:
- Estado del backend AURA
- Modelo/proveedor en uso
- Total de interacciones
- Distribución por dominio y modelo

## 🧠 Arquitectura

```
Usuario → HF Space (Gradio) → Backend AURA → IA (Gemini/Groq/OpenRouter/HF/Ollama)
                                          ↓
                                    Memoria + Web + Tools
```

## 📁 Estructura

```
aura-chat-repo/
├── app.py                  # Main Gradio app (frontend)
├── requirements.txt        # Dependencies
├── README.md               # This file
├── DEPLOY.md               # Deployment guide
├── src/
│   └── model_router.py     # Routing, cache, fallback (local fallback)
└── data/                   # Runtime logs (created automatically)
    ├── interactions.jsonl
    └── preferences.json
```

## ⚙️ Configuración

### Secrets del Space

En **Settings** → **Repository Secrets**:
- `BACKEND_URL`: URL pública del backend AURA (ej: `https://ame.onrender.com`)
- `HF_TOKEN`: token de Hugging Face (para fallback local)
- `HF_MODEL`: modelo fallback (default: `openbmb/MiniCPM5-1B`)

### Despliegue del backend

1. Despliega `ame_backend` en Render/Railway/VPS
2. Copia la URL pública (ej: `https://aura-backend.onrender.com`)
3. Configúrala como `BACKEND_URL` en el Space
4. El Space usará el backend automáticamente; sin `BACKEND_URL` usa el modelo local de HF como respaldo.

## 📝 Licencia

MIT — Ver [LICENSE](LICENSE) para más detalles.
