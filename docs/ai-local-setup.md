# Guía de Infraestructura de IA Local

## Arquitectura del Ecosistema de IA

```
┌─────────────────────────────────────────────────────────┐
│                    AURA ECOSYSTEM                        │
├─────────────┬──────────────────┬───────────────────────┤
│  Ollama     │  LM Studio       │  OpenRouter / Gemini  │
│  (Local)    │  (Local/LAN)     │  (Cloud gratuitos)    │
│  :11434     │  :1234/v1        │                        │
├─────────────┴──────────────────┴───────────────────────┤
│                    Router Inteligente                    │
│           core/ai_config.py + proxy_chat_connector.py   │
│           Fallback: OpenRouter → Gemini → LM Studio     │
├────────────────────────────────────────────────────────┤
│                    Odysseus (Docker)                     │
│           Espacio Agéntico con modelos locales          │
│           :3000 (Web) / :3001 (WebSocket)               │
├────────────────────────────────────────────────────────┤
│                    ComfyUI (Docker)                      │
│           Diseño gráfico con modelos FLUX/SDXL         │
│           :8188 (perfil "design")                       │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Conexión Ollama ↔ Odysseus

### Configurar Odysseus para usar Ollama

El `docker-compose.yml` ya incluye la variable `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

Para verificar desde el contenedor:

```bash
# Desde el host
curl http://localhost:11434/api/tags

# Probar que funciona
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "gemma3:4b", "prompt": "Hola, responde OK", "stream": false}'
```

### Configurar AURA para usar Ollama como proveedor

El router de AURA (`core/ai_config.py`) ya soporta LM Studio en `http://localhost:1234/v1`.

Para usar Ollama directamente, agrega al `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma3:4b
```

---

## 2. ComfyUI — Diseño Gráfico con Modelos Locales

ComfyUI está disponible como perfil opcional en Docker:

```bash
# Iniciar ComfyUI
docker compose --profile design up -d comfyui

# Acceder: http://localhost:8188
```

### Workflows recomendados:

| Modelo                       | Tipo           | RAM necesaria |
| ---------------------------- | -------------- | ------------- |
| FLUX.1-dev                   | Texto a imagen | 16GB+         |
| SDXL                         | Texto a imagen | 8GB+          |
| Ideogram 4.0 Open Foundation | Texto a imagen | 12GB+         |

### Descargar modelos para ComfyUI:

```bash
# Los modelos se almacenan en: docker volumen comfyui_models
# Para agregar modelos manualmente:
# 1. Descarga el .safetensors de Hugging Face
# 2. Colócalo en: ./comfyui_models/checkpoints/
# 3. Reinicia ComfyUI
```

---

## 3. Herramientas Multimedia Locales

### LTX Desktop (ByteDance)

Editor de video con IA local:

- URL: https://github.com/bytedance/LTX-Video
- Requiere: GPU NVIDIA con 8GB+ VRAM
- Instalación: `pip install ltx-video`

### Bernini (ByteDance)

Modelo de generación 3D:

- URL: https://github.com/bytedance/Bernini
- Genera modelos 3D a partir de texto o imágenes
- Requiere: GPU NVIDIA con 12GB+ VRAM

---

## 4. Pautas de Despliegue Local

### Para desarrollo (bajo consumo):

```bash
# Solo Ollama con modelo pequeño
ollama run gemma3:4b

# AURA FastAPI
.venv\Scripts\python.exe -m uvicorn core.main:app --reload

# Odysseus en Docker
docker compose up -d odysseus
```

### Para producción (máximo rendimiento):

```bash
# Todos los servicios
docker compose up -d

# Con diseño gráfico
docker compose --profile design up -d

# Verificar estado
docker compose ps
```

### Puertos de red:

| Servicio     | Puerto | Descripción                   |
| ------------ | ------ | ----------------------------- |
| AURA FastAPI | 5000   | Backend principal             |
| Odysseus     | 3000   | Espacio agéntico              |
| Odysseus WS  | 3001   | WebSocket agentes             |
| MobSF        | 8000   | Análisis de seguridad Android |
| ComfyUI      | 8188   | Diseño gráfico IA             |
| Ollama       | 11434  | API de modelos locales        |
| LM Studio    | 1234   | API alternativa local         |

---

## 5. Resolución de Problemas

### "host.docker.internal no resuelve":

En Linux, agregar:

```yaml
extra_hosts:
    - "host.docker.internal:host-gateway"
```

(Ya está configurado en el `docker-compose.yml`)

### "Ollama no responde desde Docker":

```bash
# Verificar que Ollama escuche en 0.0.0.0
$env:OLLAMA_HOST="0.0.0.0"
ollama serve
```

### "Modelo no encontrado":

```bash
# Listar modelos disponibles
ollama list

# Si no aparece, descargarlo
ollama pull gemma3:4b

# Verificar espacio en disco
df -h /  # Linux/Mac
wmic logicaldisk get size,freespace,caption  # Windows
```
