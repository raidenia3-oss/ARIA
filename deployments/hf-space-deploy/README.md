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

Asistente IA autónomo 24/7. Conversación, código, matemáticas y creatividad.

[![Hugging Face Space](https://img.shields.io/badge/🤗-Hugging%20Face%20Space-blue)](https://huggingface.co/spaces/raiden456/aura-chat)
[![GitHub](https://img.shields.io/badge/GitHub-raidenia3--oss/AURA--server.01-181717?logo=github)](https://github.com/raidenia3-oss/AURA-server.01)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 Características

- **Routing por dominio**: adapta el modelo/temperatura según código, matemáticas, creatividad o análisis
- **Memoria conversacional**: últimos 10 mensajes como contexto
- **Caché LRU**: respuestas repetidas no consumen créditos extra
- **Logging rotado**: interacciones limitadas a 5MB para no saturar el Space
- **Health check**: endpoint `/health` para ping 24/7
- **Interfaz limpia**: ChatInterface con sistema de prompts configurable

## 📊 Estado del sistema

El Space muestra en vivo:
- Estado del modelo primario
- Tamaño del caché
- Total de interacciones
- Distribución por dominio y modelo

## 📁 Estructura

```
hf-space/
├── app.py                  # Main Gradio app
├── requirements.txt        # Dependencies
├── README.md               # This file
├── DEPLOY.md               # Deployment guide
├── src/
│   └── model_router.py     # Routing, cache, fallback
└── data/                   # Runtime logs (created automatically)
    ├── interactions.jsonl
    └── preferences.json
```

## 📝 Licencia

MIT — Ver [LICENSE](LICENSE) para más detalles.
