# AURA OS v2.1 Architecture

Complete reference architecture for AURA OS.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         AURA OS v2.1                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Frontend Layer                                                 │
│  ├─ Godot Dashboard (9 panels)                                 │
│  ├─ Android APK (AME launcher)                                │
│  └─ Web UI (HTML/CSS/JS glassmorphic)                         │
│                                                                 │
│  API Layer (FastAPI, :8000)                                    │
│  ├─ Chat & Skills (16 core + extensible)                      │
│  ├─ Omniroute (300+ AI providers)                             │
│  ├─ Auth & Multi-Tenancy (JWT + bcrypt)                       │
│  ├─ C2 Framework (beaconing, task exec)                       │
│  ├─ Marketplace & Monitoring                                   │
│  └─ 83 total endpoints                                         │
│                                                                 │
│  Tools Layer                                                    │
│  ├─ Go Tools (6 binaries)                                      │
│  │  ├─ Port Scanner, DNS Resolver, Subdomain Enum            │
│  │  └─ C2 Agent/Server/Client                                 │
│  ├─ Ruby Tools (security suite)                               │
│  │  ├─ Exploit framework (SQLi, XSS, CMDi)                   │
│  │  └─ Payload generator & red team tools                 │
│  └─ Python Backend (AURA core)                                │
│                                                                 │
│  Data Layer                                                     │
│  ├─ SQLite (local persistence)                                │
│  ├─ PostgreSQL (HA production)                                │
│  ├─ Qdrant (vector embeddings)                                 │
│  ├─ ChromaDB (RAG)                                             │
│  └─ Redis (caching, sessions)                                 │
│                                                                 │
│  Infrastructure                                                 │
│  ├─ Alpine Linux (lightweight)                                │
│  ├─ Hyprland (Wayland WM)                                      │
│  ├─ Docker (containerization)                                  │
│  └─ Systemd (service management)                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Core Backend (`backend/`)

- **FastAPI Application** (`main.py`) — 83 routes
- **21 Modules** — Skills, networking, security, monitoring
- **Omniroute** (`backend/omniroute/`) — Multi-provider AI gateway
- **React Loop** (`backend/agents/react_loop.py`) — ReAct agent with fallback
- **Kilo Bridge** (`backend/agents/kilo_bridge.py`) — Agent orchestrator

### Go Tools (`aura-os/go-tools/`)

6 standalone CLI tools with **zero external dependencies**:

| Tool | Purpose | Concurrency |
|------|---------|-------------|
| `aura-scanner` | Port scanner | 100+ goroutines |
| `aura-resolver` | DNS resolver | Batch queries |
| `aura-enum` | Subdomain enum | 1000+/min |
| `aura-c2-server` | C2 controller | REST API |
| `aura-c2-agent` | Beaconing agent | HTTP fallback |
| `aura-c2-client` | CLI controller | Interactive |

### Ruby Tools (`aura-os/ruby-tools/`)

5 modules for security testing:

| Module | Classes | Features |
|--------|---------|----------|
| `exploit_framework.rb` | SQLiTester, XSSTester, CommandInjectionTester, LDAPInjectionTester, PathTraversalTester | 5 vulnerability types |
| `payload_generator.rb` | ReverseShell, WebShell, Encoder, Shellcode | 15+ payloads |
| `red_team_tools.rb` | CredentialTester, NetworkAttacks, PrivilegeEscalation, PostExploitation | Full pentest lifecycle |
| `bin/aura-pentest` | CLI orchestrator | 7 subcommands |
| `lib/aura_tools.rb` | Main module | Plugin loading |

### Distribution (`aura-os/`)

| Component | Description |
|-----------|-------------|
| `Dockerfile` | Alpine 3.18 + all tools |
| `hyprland.conf` | Wayland WM config |
| `waybar.conf` | Status bar (CPU, mem, net, audio, batt) |
| `entrypoint.sh` | Startup script (backend + tools) |
| `post-install.sh` | Alpine setup (Go, Ruby, Python) |
| `build-distro-hardened.sh` | CI build script |
| `docs/USB-GUIDE.md` | USB boot guide |

## Data Flow

```
User Request → FastAPI → Auth/JWT → Skill Router → [Local AI / Omniroute] → Response
                              ↓
                    Cache (Redis) + DB (SQLite/Postgres)
```

### Omniroute Flow

```
Client → /api/chat/omniroute
   → ProviderManager.health_check()
   → Find best provider (latency/cost/capability)
   → Route to provider API
   ↳ Fallback: LOCAL (Ollama) if all fail
   → Response + metrics
```

### C2 Flow

```
Agent → HTTP beacon → C2 Server → Task Queue
   ← Execute task ← Receive task ← Assign task
```

## Deployment Targets

### 1. USB Boot (Primary)
- Alpine Linux 3.18
- Hyprland Wayland desktop
- All tools pre-installed
- ~900MB total image size

### 2. Docker Container
- ghcr.io/your-repo/aura:v2.1
- Port 8000 exposed
- SQLite local, mounts for persistence

### 3. Windows (Dev/Test)
- Python venv
- WebView2 frontend
- All Python/Ruby scripts work

### 4. Android (AME)
- APK with Godot engine
- WebSocket sync with backend
- mDNS discovery (aura.local)

## Security Model

```
Internet → HTTPS → JWT Auth → API Gateway
              ↳ Rate Limiting (per-API-key)
              ↳ CORS/CSRF protection
              ↳ Input sanitization
              ↳ Output encoding

Backend → mTLS → Provider APIs
         ↳ Encryption at rest
         ↳ Audit logging
```

## File Organization

```
aura/
├── backend/                    # Python backend (21 modules, 83 routes)
│   ├── main.py                # Entry point
│   ├── omniroute/             # Multi-provider gateway
│   ├── agents/                # ReAct Loop, Kilo Bridge
│   ├── skills/                # 16 core + custom skills
│   ├── monitoring/            # Metrics, distributed
│   ├── security_routes.py     # Auth, compliance
│   └── ...
├── tests/                     # 7 unit + 9 integration tests
├── scripts/                   # Build & release scripts
├── .github/workflows/         # CI/CD pipelines
├── AURA_APP/                  # Standalone executable
│   ├── standalone.py
│   ├── frontend/
│   └── backend/
├── aura-os/                   # Distribution layer
│   ├── distro-builder/        # Dockerfile + build scripts
│   ├── go-tools/              # 6 Go CLI tools
│   ├── ruby-tools/            # 5 Ruby security modules
│   ├── hyprland.conf          # WM config
│   ├── waybar.conf            # Status bar
│   ├── entrypoint.sh          # Startup
│   ├── post-install.sh        # Setup
│   └── docs/                  # USB guide, pentest guide
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # This file
│   └── ...
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── ANNOUNCEMENT.md
└── VERSION
```

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python / FastAPI | 3.11 / 0.141.1 |
| ORM | SQLAlchemy | 2.0 |
| Auth | JWT + bcrypt | jose 3.3 |
| AI Router | Native (ai_router.py) | — |
| AI Providers | OpenRouter, Gemini, Groq, OpenAI, Local | 300+ models |
| Go Tools | Go (stdlib-only) | 1.21 |
| Ruby Tools | Ruby + Bundler | 3.2 |
| OS | Alpine Linux + Hyprland | 3.18 |
| Container | Docker | Latest |
| CI/CD | GitHub Actions | — |
| Monitoring | Prometheus + Grafana | — |
| Tracing | OpenTelemetry | — |
| Cache | Redis | — |

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feat/new-feature`)
3. Run lint + tests (`python -m pytest tests/`)
4. Commit with conventional messages
5. Push and open PR

## License

MIT License — see [LICENSE](../LICENSE) for details.

Commercial licensing available: commercial@aura-os.dev
