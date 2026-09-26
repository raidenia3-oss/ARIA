# AURA - Guía de Despliegue Docker

## Requisitos

- Docker Engine 20.10+
- Docker Compose V2+
- 4GB RAM mínimo (8GB recomendado)
- 10GB espacio en disco

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ aura-backend │  │ aura-frontend│  │  redis   │ │
│  │  :8000       │  │  :80         │  │  :6379   │ │
│  │ Python/      │  │ Nginx + React│  │  Cache   │ │
│  │ FastAPI      │  │              │  │          │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│         │                  │                   │    │
│         └──────────────────┼───────────────────┘    │
│                            │                        │
│  Volúmenes persistentes:                              │
│  • aura_vector_db  → /app/vector_db (ChromaDB)        │
│  • aura_sqlite_db  → /app/sqlite (Bases locales)     │
│  • aura_redis_data → Redis persistente               │
│  • ./logs          → Logs del backend                │
└─────────────────────────────────────────────────────┘
```

## Inicio Rápido

```bash
# 1. Clonar el repositorio
git clone <repo-url> AURA
cd AURA

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys (OPENROUTER_API_KEY, GEMINI_API_KEY, etc.)

# 3. Iniciar stack completo (primer build tarda ~5-10 min)
docker compose up --build -d

# 4. Ver logs en tiempo real
docker compose logs -f

# 5. Verificar estado
docker compose ps
```

## Acceso a Servicios

| Servicio      | URL Local                    | Descripción         |
| ------------- | ---------------------------- | ------------------- |
| Frontend AURA | http://localhost             | Panel web principal |
| API Backend   | http://localhost:8000        | REST API + docs     |
| Health Check  | http://localhost:8000/health | Estado del backend  |
| Redis         | localhost:6379               | Cache interno       |

## Comandos Útiles

```bash
# Ver logs de un servicio específico
docker compose logs -f aura-backend

# Reiniciar un servicio
docker compose restart aura-backend

# Detener todo (preserva volúmenes)
docker compose down

# Detener y eliminar volúmenes (CUIDADO: borra datos)
docker compose down -v

# Rebuild de un solo servicio
docker compose build aura-backend
docker compose up -d aura-backend

# Ejecutar comando dentro del backend
docker compose exec aura-backend python -c "import aura_api; print('OK')"

# Acceder a shell del backend como root (debug)
docker compose exec aura-backend sh

# Estadísticas de recursos
docker stats aura_backend aura_frontend aura_redis

# Backup de volúmenes
docker run --rm -v aura_vector_db:/data -v $(pwd):/backup alpine tar czf /backup/vector_db_backup.tar.gz /data
```

## Configuración Avanzada

### Variables de Entorno Principales (.env)

```env
# API Keys (OBLIGATORIO)
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...

# Base de Datos
DATABASE_URL=sqlite:///./sqlite/aura.db
VECTOR_DB_PATH=/app/vector_db

# Redis
REDIS_URL=redis://aura-redis:6379/0

# Servidor
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
WORKERS=2
```

### Escalado del Backend

```bash
# Escalar a 4 workers
docker compose up -d --scale aura-backend=4

# O editar docker-compose.yml:
# deploy:
#   replicas: 4
#   resources:
#     limits:
#       cpus: '2'
#       memory: 2G
```

### Proxy Reverso Externo

Para exponer AURA en internet, edita `nginx.conf`:

```nginx
server {
    listen 80;
    server_name aura.tu-dominio.com;

    # Let's Encrypt / SSL
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/aura.tu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aura.tu-dominio.com/privkey.pem;

    # ... resto de configuración ...
}
```

## Healthchecks

- **Backend**: `GET /health` → `{"status": "ok"}`
- **Frontend**: `GET /` → HTML response 200
- **Redis**: `redis-cli ping` → `PONG`

## Troubleshooting

### Backend no inicia

```bash
# Ver logs detallados
docker compose logs aura-backend

# Verificar .env
docker compose exec aura-backend env

# Verificar permisos de volúmenes
docker compose exec aura-backend ls -la /app/vector_db
```

### Frontend no carga

```bash
# Verificar build
docker compose logs aura-frontend

# Reforzar build
docker compose build --no-cache aura-frontend
docker compose up -d aura-frontend
```

### Redis lleno

```bash
# Ver memoria usada
docker compose exec aura-redis redis-cli info memory

# Limpiar cache (CUIDADO)
docker compose exec aura-redis redis-cli FLUSHDB
```

## Modo Desarrollo (sin Docker)

```bash
# Backend
cd AURA_Core
pip install -r requirements.txt
uvicorn aura_api:app --reload --port 8000

# Frontend
cd aura-ui
npm install
npm run dev
```

## Estructura de Archivos Docker

```
AURA/
├── config/backend.Dockerfile          # Build backend Python
├── config/frontend.Dockerfile         # Build frontend Node + Nginx
├── config/nginx.conf                  # Configuración Nginx
├── config/docker-compose.yml          # Orquestación
├── .dockerignore               # Excluir del build
├── .env                        # Variables locales (NO commit)
└── DOCKER_DEPLOY.md            # Esta guía
```

## Próximos Pasos

- [ ] Configurar CI/CD con GitHub Actions
- [ ] Agregar monitoreo (Prometheus + Grafana)
- [ ] Configurar backup automático de volúmenes
- [ ] Implementar rolling updates con `docker compose up --update-order start-first`

---

**AURA DevOps** | Containerización: Docker + Compose | Puerto: 80/8000
