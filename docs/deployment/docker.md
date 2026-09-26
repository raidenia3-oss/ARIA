# Deployment con Docker

Guía para levantar AURA completo con Docker Compose.

## Prerrequisitos

- Docker 24+
- Docker Compose v2+
- 4 GB RAM libres como mínimo
- PowerShell o Git Bash en Windows

## Variables

Copia `docker/.env` a `.env.ai` y completa con tus secretos:

```env
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=
```

## Comandos

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f backend
```

## URLs

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Volúmenes

- `ollama_data`: modelos de Ollama
- `./models`: modelos locales
- `./fine-tuned-ame`: adaptadores LoRA
- `./training/data`: datos de entrenamiento

## Troubleshooting

- Backend no inicia: revisa `docker compose logs backend`
- Ollama no responde: `docker compose logs ollama`
- Puerto ocupado: cambia mappings en `docker-compose.yml`