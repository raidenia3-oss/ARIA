# Producción AURA

Arquitectura, deployment, monitoreo y troubleshooting para entornos productivos.

## Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Ollama        │
│   Next.js       │◄──►│   FastAPI       │◄──►│   Local LLM     │
│   Puerto 3000   │    │   Puerto 8000   │    │   Puerto 11434  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         │                       │
         │                       ▼
         │              ┌─────────────────┐
         │              │   Redis         │
         │              │   Cache         │
         │              │   Puerto 6379   │
         │              └─────────────────┘
         │
         ▼
┌─────────────────┐
│   Usuarios      │
│   Web/Discord   │
└─────────────────┘
```

## Variables de entorno

### Backend (.env.ai)
```env
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=
AURA_BACKEND_URL=http://localhost:8000
```

### Frontend
```env
NEXT_PUBLIC_AURA_BACKEND_URL=https://tu-backend.up.railway.app
```

## Procedimiento de deploy

1. Build y push de imágenes Docker
2. Deploy en Railway/Render
3. Verificar `/health`
4. Configurar volúmenes persistentes
5. Ejecutar `training/scripts/cloud_backup.py`

## Rollback

- Restaurar backup de LoRA desde `fine-tuned-ame/backups/`
- Redesplegar imagen anterior
- Verificar `/health`

## Monitoreo

- `logs/metrics.jsonl`: métricas de requests
- `logs/observability_report.json`: reporte diario
- `logs/alerts.jsonl`: alertas activas

## Troubleshooting

### Ollama OOM
- Reducir `max_new_tokens` en inferencia
- Usar CPU-only en Railway
- Aumentar memoria del servicio

### Timeouts
- Ajustar timeouts en `ame_backend/src/services/ai_engine.py`
- Usar cache Redis
- Limitar rate de requests

### Rate limits
- Implementar cache en Redis
- Aumentar `_RATE_LIMIT_MAX` en `main.py`
- Usar colas de tareas

## Checklist pre-deploy

- [ ] Variables de entorno configuradas
- [ ] Modelos descargados en volumen
- [ ] Tests pasando (`make test`)
- [ ] Docker build exitoso
- [ ] `/health` responde correctamente
- [ ] Backup de LoRA existente
- [ ] Alertas configuradas