# AURA OS Knowledge Base

Complete reference for AURA OS v2.1 and beyond.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Architecture](#architecture)
3. [API Reference](#api-reference)
4. [Deployment](#deployment)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)
7. [Advanced Topics](#advanced-topics)

## Getting Started

### Installation (5 minutes)

```bash
# Option 1: Local development
git clone https://github.com/TU_USUARIO/AURA.git
cd AURA
pip install -r backend/requirements.txt
python backend/main.py

# Option 2: Docker
docker-compose up

# Option 3: USB Boot
# Download from releases and boot from USB
```

### First Steps

After installation, verify:

```bash
# Check API
curl http://localhost:8000/api/health

# List providers
curl http://localhost:8000/api/providers

# Send a message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello AURA"}'
```

### Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/aura_db

# Cache
REDIS_URL=redis://localhost:6379

# AI Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...

# Omniroute
OMNIROUTE_URLS=http://localhost:8081,http://localhost:8082
OMNIROUTE_FALLBACK=local

# Security
JWT_SECRET=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# Logging
LOG_LEVEL=info
```

## Architecture

### System Components

```
Frontend Layer
  ├── Godot Dashboard (9 panels)
  ├── Android APK (AME)
  └── Web UI (HTML/CSS/JS)

API Layer (FastAPI :8000) — 117 routes total
  ├── Health & System (5 routes)
  ├── Chat & AI (8 routes)
  ├── Omniroute (7 routes)
  ├── Auth & Multi-tenancy (15 routes)
  ├── C2 Framework (6 routes)
  ├── Voice & TTS (7 routes)
  ├── Memory (4 routes)
  ├── Skills (3 routes)
  ├── Agent/Kilo (5 routes)
  ├── Automation (12 routes)
  ├── Plugins (4 routes)
  ├── Mobile (3 routes)
  └── Network (5 routes)

Tools Layer
  ├── Go Tools (6 binaries — scanner, resolver, enum, c2-agent, c2-server, c2-client)
  ├── Ruby Tools (discord-bot, dsl-compiler, security suite)
  └── Python Backend (AURA core, omniroute, skills registry)

Data Layer
  ├── PostgreSQL (primary)
  ├── Redis (cache + rate limiting)
  ├── Qdrant (vectors)
  └── ChromaDB (RAG)
```

### Route Categories

| Category | Routes | Key Endpoints |
|----------|--------|---------------|
| Health | 5 | `/health`, `/api/health`, `/api/status`, `/metrics` |
| Chat | 8 | `/api/chat`, `/api/chat/stream`, `/api/chat/omniroute` |
| Omniroute | 7 | `/api/providers`, `/api/providers/best`, `/api/omniroute/health` |
| Auth | 15 | `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/auth/sessions` |
| Admin | 3 | `/api/admin/users`, `/api/admin/users/{user_id}` |
| Skills | 3 | `/api/skills`, `/api/skills/{skill_name}`, `/api/skills/search` |
| Voice | 7 | `/api/tts`, `/api/tts/voices`, `/api/voice/transcribe` |
| Memory | 4 | `/api/memory/recent`, `/api/memory/save`, `/api/memory/search` |
| Agent | 5 | `/api/agent/status`, `/api/agents/kilo/delegate` |
| Automation | 12 | `/api/automation/rules`, `/api/automation/monitor` |
| Plugins | 4 | `/api/plugins`, `/api/plugins/reload` |
| Mobile | 3 | `/api/mobile/discovery`, `/api/mobile/devices` |
| Network | 4 | `/api/wifi/scan`, `/api/network/topology` |
| System | 5 | `/api/system/status`, `/api/system/telemetry` |
| C2 | 6 | `/api/agent/command`, `/api/device/automate` |
| Orchestrator | 2 | `/api/orchestrator`, `/api/orchestrator/register` |
| Training | 3 | `/api/training/start`, `/api/training/status` |
| Other | 12 | `/api/brain`, `/api/feedback`, `/api/news/recommend` |

### Omniroute Integration

```python
# Omniroute is integrated as a multi-provider AI gateway
# Routes prefixed with /api/ in backend/main.py:lines 1577-1676

# Key features:
# - Automatic provider rotation
# - Context relay between providers
# - Fallback to ReactLoop local when providers fail
# - Stats: circuit breaker state, latency, success rate
```

## API Reference

### Authentication

All API endpoints (except `/health` and `/api/health`) require a valid JWT token:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/skills
```

#### Register

```bash
POST /api/auth/register
BODY: {"username": "user", "email": "user@example.com", "password": "secret123"}
```

#### Login

```bash
POST /api/auth/login
BODY: {"username": "user", "password": "secret123"}
RESPONSE: {"access_token": "...", "token_type": "bearer"}
```

### Chat (Omniroute)

```bash
POST /api/chat
BODY: {"message": "Hello", "session_id": "abc123", "skill_id": "chat"}
```

Uses omniroute with automatic provider rotation:
1. Primary provider (configurable)
2. Fallback providers in rotation
3. Local ReactLoop if all external providers fail

### Provider Management

```bash
GET  /api/providers                 # List all providers
GET  /api/providers/best            # Get best provider by model type
GET  /api/providers/stats           # Provider performance stats
GET  /api/omniroute/health          # Omniroute health check
```

### Skills

```bash
GET  /api/skills                    # List available skills
POST /api/skills/{skill_name}      # Execute a skill
GET  /api/skills/search?query=...   # Search skills
```

Built-in skills include: `system.status`, `system.time`, `system.ping`, `system.scan`, `web.search`, `web.weather`, `files.read`, `files.write`.

## Deployment

### Quick Deploy Options

| Platform | Complexity | Cost | Notes |
|----------|-----------|------|-------|
| PythonAnywhere | Easy | Free tier available | Best for beginners |
| Railway | Easy | Paid tiers | Recommended for production |
| Render | Medium | Free tier available | render.yaml included |
| AWS Lambda | Complex | Pay-per-use | Serverless, needs mangum |
| DigitalOcean | Medium | $5+/mo | app.yaml included |
| Self-hosted | Hard | Variable | Full control |

### Pre-Launch Checklist

See `docs/PRODUCTION-CHECKLIST.md` for the complete 50+ point checklist including:
- All 117 routes responding correctly
- Authentication working (JWT tokens)
- Rate limiting configured
- Security audit passed (0 critical issues)
- Load test passed (100+ concurrent users)
- Backup schedule configured

### Post-Release Monitoring

Run `scripts/post-release-monitor.sh` to track:
- GitHub release downloads
- Stars, forks, issues
- CI/CD pipeline status
- Docker image pulls
- Discord webhook notifications (optional)

## Troubleshooting

### API Returns 500

1. Check backend logs:
```bash
python backend/main.py 2>&1 | tail -50
```

2. Verify configuration:
```bash
source .env
echo $DATABASE_URL
echo $GEMINI_API_KEY
```

3. Check LOG_LEVEL — must be uppercase or normalized by `backend/logging/config.py`.

### Omniroute "No healthy providers"

This is expected in local dev without the omniroute server running. The fallback uses ReactLoop locally.

To run omniroute server locally:
```bash
pip install -r backend/omniroute/requirements.txt
python -m omniroute.server --port 8080
```

### Database Connection Errors

```bash
# Check database
python backend/db.py  # tests connection

# Run migrations
python backend/alembic/versions/upgrade_db.py

# Reset database
rm -f backend/aura.db && python backend/db.py
```

### Missing Dependencies

Common missing packages:
```bash
pip install selenium redis structlog prometheus_client \
  opentelemetry-exporter-otlp-proto-grpc httpx
```

### Windows Specific Issues

1. Use PowerShell: `.\aura-os\scripts\start-aura-app.ps1`
2. Build executable: See AGENTS.md build command
3. Disk check: `.\aura-os\scripts\check_disk_readonly.ps1`

### Go Tools Not Compiling

```bash
# Install Go 1.21+
# Build all tools
cd aura-os/go-tools
make build

# Individual builds
go build -o bin/aura-scanner ./cmd/scanner
```

## FAQ

### How many API routes does AURA OS have?
117 routes across 14 categories (health, chat, omniroute, auth, skills, voice, memory, agent, automation, plugins, mobile, network, system, C2, orchestrator, training).

### Is Go required?
No. Go tools are optional for scanning and C2 operations. Python backend runs independently.

### Can I use local models?
Yes. Set `AI_PROVIDER=local` with `LOCAL_LFM_BASE_URL` and `LOCAL_LFM_MODEL` for Ollama.

### What providers does Omniroute support?
Gemini, Groq, OpenRouter, HuggingFace, and local models via Ollama.

### Is the frontend included?
Yes. The Godot dashboard, web UI, and mobile APK are all part of the AURA OS package.

## Advanced Topics

### Custom Skill Development

```python
# Create: backend/skills/custom/my_skill.py
from backend.skills.base import SkillBase

class MySkill(SkillBase):
    @property
    def name(self) -> str:
        return "my_skill"

    def execute(self, input: str) -> str:
        return f"Processed: {input}"
```

### Omniroute Provider Rotation

The omniroute manager (`backend/omniroute/manager.py`):
1. Tracks provider health (circuit breaker)
2. Rotates providers on failure
3. Maintains latency and success rate metrics
4. Falls back to local ReactLoop

### Go Tool Suite

Six Go utilities (`aura-os/go-tools/`):

| Tool | Purpose |
|------|---------|
| `aura-scanner` | Network discovery & port scanning |
| `aura-resolver` | DNS resolution & domain analysis |
| `aura-enum` | Enumeration of HTTP endpoints |
| `aura-c2-agent` | C2 implant for remote systems |
| `aura-c2-server` | C2 command & control server |
| `aura-c2-client` | C2 operator client |

Built as static binaries: `CGO_ENABLED=0 go build -ldflags "-s -w"`

### Ruby Security Tools

Located in `packages/discord-bot/` and `packages/ruby-tools/`:
- Discord bot with slash commands
- DSL compiler for security rules
- Exploit generation utilities

### Performance Profiling

```bash
# Run load tests
./scripts/load-test.sh http://localhost:8000 10 60

# Memory profiling
python -m memory_profiler backend/main.py

# CPU profiling
python profile_cpu.py
```

### Security Audit

```bash
# Run automated security audit
./scripts/security-audit.sh

# Bandit static analysis
bandit -r backend/ -ll

# Dependency check
safety check --file backend/requirements.txt
```

---

**Reference Version**: AURA OS v2.1.0  
**Last Updated**: September 2, 2026  
**Documentation Source**: `docs/KNOWLEDGE-BASE.md`
