MASTER PROMPT - ARIA v6.0 Axum Migration (Parallel to USB-ARIA)

You are a Kilo agent working in parallel with another agent that is building USB-ARIA (portable autonomous agent). Your task is the Axum backend migration for ARIA v6.0.

## Your Mission
Continue developing the Axum (Rust) backend that replaces the current FastAPI backend. The USB-ARIA agent handles PC state detection, background tasks, and Discord reporting. You handle the main backend API.

## Current State
- Existing Axum POC: v6/axum-poc/ (11 endpoints, compiles but needs expansion)
- FastAPI backend: ARIA_APP/backend/app.py (2696 lines, 312 routes)
- FastAPI running on port 8001 (already running)
- LocalTunnel: aria-backend.loca.lt (503 currently, need reconnect)
- USB-ARIA agent: usb-aria/aria_usb_agent.py (just created, polls /api/pc/state and /api/daemon/*)

## Your Tasks (in priority order)
1. Add /api/pc/state endpoint to Axum POC (POST - returns PC activity state JSON)
2. Add /api/daemon/task endpoint (POST - handle get_pending, report_status, submit_result)
3. Add /api/daemon/result endpoint (POST - receive task results from USB agents)
4. Migrate core endpoints from FastAPI to Axum:
   - /api/system/status (GET) - system metrics (CPU, RAM, disk)
   - /api/tools/execute (POST) - tool execution
   - /api/research (POST) - social research agent
   - /api/chat (POST) - chat with Ollama via reqwest
5. Run on port 8002 (avoid conflict with FastAPI on 8001)
6. Test all endpoints with curl

## Key Code Locations
- FastAPI app: C:\Users\User\Downloads\AURA\ARIA_APP\backend\app.py
- Axum POC: C:\Users\User\Downloads\AURA\v6/axum-poc/src/main.rs
- OrbVisual: C:\Users\User\Downloads\AURA\v5/src/components/OrbVisual/OrbVisual.tsx
- Backend scripts: start_backend.bat, start_tunnel.bat, start_autonomous.bat

## Coordination
- Use Discord webhook reporting for your own status (same channel)
- When you add an endpoint, USB-ARIA agent will automatically use it
- The localtunnel gives you a public URL (aria-backend.loca.lt) for webhook integration

## Commands
- Build: cd v6/axum-poc && cargo run
- Test: curl http://localhost:8002/health
- Format: cargo fmt
- Check: cargo clippy 2>&1 | grep warning

## Discord Reporting
Use the same webhook URL to post development progress to #aria-status. Report:
- When new endpoints are ready
- Build status
- Integration with USB-ARIA agent

## Git
- Branch: feature/v6.0-axum-migration (already created)
- Commit incrementally
- DO NOT commit until agent gives go-ahead

Start by examining the existing FastAPI routes you need to replicate, then expand the Axum POC.

DO NOT pause USB-ARIA work happening in this session. Sync via Discord #aria-status.

## Quick Start
```bash
cd C:\Users\User\Downloads\AURA\v6/axum-poc
cargo run  # on port 8002
curl http://localhost:8002/health
```

## Current FastAPI Routes (from app.py)
Focus on these critical endpoints for USB-ARIA coordination:
- POST /api/pc/state - returns {"active": true/false, "idle_seconds": N, "session_user": "name"}
- POST /api/daemon/task - handles USB agent task coordination
- POST /api/daemon/result - receives results from USB agents
- POST /api/daemon/heartbeat - USB agent keeps alive

Then migrate: chat, skills, memory, system status, research endpoints.