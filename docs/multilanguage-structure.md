# AURA multi-language structure

The repository now uses a safer top-level layout for the multi-language expansion while preserving the existing backend and frontend entry points.

## Top-level layout

- `backend/` keeps the FastAPI entry point and integration endpoints.
- `frontend/` remains the Next.js front-end.
- `services/discord-bot/` hosts the Ruby Discord bot.
- `services/gesture-control/` hosts the Python gesture controller.
- `services/voice-commands/` hosts the Python voice-command router.
- `services/dsl-compiler/` hosts the Ruby DSL compiler.
- `docker/` stores compose assets and Dockerfiles.
- `tests/` and `data/` store validation assets and sample payloads.

## Phase 8 architecture

- **Cierre final**: README definitivo, documentación completa, prompt de cierre.
- **HF Space productivo**: scaffold `hf-space/` con Gradio ChatInterface, integrado a docker-compose y frontend.
- **AURA Core integrado**: event bus, agent orchestrator, keep-alive, live reload funcionales y documentados.
- **Bug fixes**: corregido import datetime en `AURA_Core/event_bus.py`.
- **Deploy completo**: docker-compose con backend, frontend, discord-bot, hf-space, postgres, redis. Healthchecks, restart always, dependencias condicionales.
- **Observabilidad**: Prometheus `/metrics`, rate limiting, CORS, alertas Discord desde backend.

## Verified test coverage

- Python: 18 passed (integration 9, gesture-control 4, voice-commands 4, multilanguage scaffolds 2).
- Ruby: specs disponibles en `services/discord-bot/spec` y `services/dsl-compiler/spec`.
- Load tests: Locust TaskSet con health, status, logs, metrics, gesture predict, voice transcribe, restart, deploy.

## Local development

- Backend: `python backend/main.py`
- Frontend: `npm run dev` en `frontend/`
- Discord bot: `ruby services/discord-bot/bot.rb`
- HF Space: `python hf-space/app.py`
- Tests Python: `pytest services/gesture-control/tests services/voice-commands/tests tests/integration tests/unit`
- Tests Ruby: `rspec services/discord-bot/spec services/dsl-compiler/spec`
- Load tests: `locust -f tests/load/locustfile.py --host http://localhost:8000`

## Production deployment

- `docker-compose up --build`
- Backend: 8000, Frontend: 3000, HF Space: 7860, Postgres: 5432, Redis: 6379
- Configurar variables de entorno según sección en README.md
