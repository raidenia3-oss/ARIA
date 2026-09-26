# Deployment en Railway

Guía paso a paso para desplegar AURA en Railway.

## 1. Crear proyecto

1. Ve a https://railway.app y crea una cuenta
2. Nuevo proyecto → Deploy from GitHub repo
3. Selecciona el repositorio de AURA

## 2. Backend (FastAPI)

- Agrega un servicio "Backend"
- Build: Dockerfile en `docker/backend.Dockerfile`
- Puerto: 8000
- Variables de entorno:
  ```
  GEMINI_API_KEY=
  GROQ_API_KEY=
  OPENROUTER_API_KEY=
  HF_TOKEN=
  AURA_BACKEND_URL=http://localhost:8000
  ```
- Volúmenes:
  - `/app/models` → `./models`
  - `/app/fine-tuned-ame` → `./fine-tuned-ame`
  - `/app/training/data` → `./training/data`

## 3. Ollama

- Agrega un servicio "Ollama"
- Imagen: `ollama/ollama:latest`
- Puerto: 11434
- Comando de inicio: `ollama serve`
- Variables:
  ```
  OLLAMA_HOST=0.0.0.0
  ```
- Volumen: `/root/.ollama` (para persistir modelos)
- Nota: Railway no garantiza GPU; el modelo corre en CPU

## 4. Frontend (Next.js)

- Agrega un servicio "Frontend"
- Build: `frontend/Dockerfile`
- Puerto: 3000
- Variables:
  ```
  NEXT_PUBLIC_AURA_BACKEND_URL=https://tu-backend.up.railway.app
  ```

## 5. Verificación

```bash
curl https://tu-backend.up.railway.app/health
curl https://tu-frontend.up.railway.app
```

## 6. Troubleshooting

- Backend no inicia: revisa logs en Railway, verifica que `ame_backend/src/main.py` compile
- Ollama no responde: verifica que el servicio esté corriendo y que el modelo esté descargado
- Timeouts: Railway tiene límite de 15min por request; ajusta timeouts en el backend