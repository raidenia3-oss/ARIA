# ARIA v6.0 - Distributed Autonomous System Status
## Phase L.4: USB-ARIA + Axum Migration

### Architecture Overview
```
┌─────────────────────────────────────────────────────┐
│                ARIA DISTRIBUTED SYSTEM              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  USB Agent (Portable)              PC (Main)         │
│  ├─ usb-aria/aria_usb_agent.py     ├─ FastAPI (8001) │
│  ├─ Polls /api/pc/state            ├─ Axum (8002)    │
│  ├─ Executes background tasks        └─ Neural Brain │
│  ├─ Discord reporting                                │
│  ├─ start_usb_agent.bat                              │
│                                                     │
│  ┌─────────────────────────────────┐               │
│  │    DISCORD HUB                 │               │
│  ├─ #aria-status (monitoring)      │               │
│  ├─ #aria-tasks                    │               │
│  ├─ #aria-improvements             │               │
│  └─ #aria-logs                     │               │
│                                                     │
│  Mobile (Airi - Android)                           │
│  ├─ Termux                                           │
│  ├─ React Native UI                                    │
│  ├─ Sync via Discord/WebSocket                         │
│  └─ Remote commands                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Running Services
| Service           | Port | Status   | Script                 |
|-------------------|------|----------|------------------------|
| FastAPI Backend   | 8001 | ✅ Running (PID 24312) | start_backend.bat       |
| Axum Server       | 8002 | ✅ Running (PID 17364) | cargo run               |
| LocalTunnel       | 80   | ✅ Running           | start_tunnel.bat        |
| Autonomous Agent  | N/A  | ✅ Running (PID 33068) | start_autonomous.bat   |

### Axum Endpoints (Port 8002)
- GET `/health` - Health check
- GET `/api/system/status` - System status
- POST `/api/chat` - Chat endpoint
- POST `/api/pc/state` - **USB-ARIA: Query PC state**
- POST `/api/daemon/task` - **USB-ARIA: Task coordination**
- POST `/api/daemon/result` - **USB-ARIA: Submit task results**
- POST `/api/daemon/heartbeat` - **USB-ARIA: Agent heartbeat**
- GET `/api/skills` - Skills list
- POST `/api/skills/run` - Execute skill
- GET `/api/agents/status` - Swarm status
- POST `/api/agents/execute` - Execute agent
- POST `/api/memory/store` - Store memory
- POST `/api/memory/search` - Search memory

### USB-ARIA Agent (usb-aria/)
- **File**: `aria_usb_agent.py`
- **Config**: `ARIA_BACKEND_URL=http://127.0.0.1:8002`
- **Discord**: Webhook in `.env`
- **Protocol**: Polls `/api/pc/state`, `/api/daemon/task`, `/api/daemon/heartbeat`

### Axum Migration Status
- **Branch**: `feature/v6.0-axum-migration`
- **POC Location**: `v6/axum-poc/`
- **Dependencies**: axum 0.7, tokio 1.x, serde, serde_json
- **Modules**: 20 modules (core, chat, skills, agents, memory, voice, vision, system, files, web, proactive, evolution, learning, computer, github, social, auth, admin, self_improvement, daemon)
- **Build**: ✅ Compiles (only warnings)
- **Port**: 8002 (parallel to FastAPI on 8001)

### USB-ARIA Agent Status
- **Location**: `usb-aria/aria_usb_agent.py`
- **Actions**: Detects PC activity, executes background tasks, reports to Discord

### Next Steps
1. [ ] Start USB agent: `start_usb_agent.bat`
2. [ ] Add more daemon endpoints to Axum (task submission from ARIA)
3. [ ] Connect Axum to SQLite (aura.db)
4. [ ] Migrate chat endpoint to call Ollama via reqwest
5. [ ] Deploy USB-ARIA to actual USB drive with Linux minimal