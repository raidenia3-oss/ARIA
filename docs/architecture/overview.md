# Arquitectura AURA

## Visión general

```
Frontend (Next.js) -> Backend (FastAPI) -> AI Engine -> Providers (local/cloud)
                                         |
                                         +-> Observability -> logs/metrics
                                         |
                                         +-> Multi-modal tools (image/audio/pdf)
```

## Componentes

- Backend: `ame_backend/src/main.py`
- AI Engine: `ame_backend/src/services/ai_engine.py`
- Observabilidad: `ame_backend/src/observability.py`
- Multi-modal: `ame_backend/src/tools/multimodal.py`
- Frontend: `frontend/app/`
- Docker: `docker-compose.yml`

## Flujo

1. Usuario envía mensaje
2. Backend valida y enruta
3. AI Engine consulta proveedores
4. Respuesta se registra en métricas
5. Frontend muestra respuesta