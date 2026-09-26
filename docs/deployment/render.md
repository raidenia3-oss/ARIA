# Deployment en Render

Guía paso a paso para desplegar AURA en Render.

## 1. Crear servicios

### Backend
- Tipo: Web Service
- Build: Docker
- Dockerfile: `docker/backend.Dockerfile`
- Puerto: 8000
- Variables:
  ```
  GEMINI_API_KEY=
  GROQ_API_KEY=
  OPENROUTER_API_KEY=
  HF_TOKEN=
  ```
- Volúmenes:
  - `/app/models` → `./models`
  - `/app/fine-tuned-ame` → `./fine-tuned-ame`

### Ollama
- Tipo: Background Worker
- Imagen: `ollama/ollama:latest`
- Comando: `ollama serve`
- Variables:
  ```
  OLLAMA_HOST=0.0.0.0
  ```
- Volumen: `/root/.ollama`

### Frontend (opcional)
- Tipo: Static Site
- Build: Docker
- Dockerfile: `frontend/Dockerfile`
- Puerto: 3000
- Variables:
  ```
  NEXT_PUBLIC_AURA_BACKEND_URL=https://tu-backend.onrender.com
  ```

## 2. Verificación

```bash
curl https://tu-backend.onrender.com/health
```

## 3. Notas

- Render free tier duerme después de 15min de inactividad
- Ollama en CPU puede ser lento para modelos grandes
- Usa `docker compose config` para validar sintaxis antes de push