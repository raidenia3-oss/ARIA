MASTER PROMPT - ARIA v6.0 Axum Migration Agent

You are working on the ARIA v6.0 Axum (Rust) backend migration IN PARALLEL with another agent building USB-ARIA.

## Current Status
- **Repo**: https://github.com/raidenia3-oss/ARIA (branch: `feature/v6.0-axum-migration`)
- **Axum POC**: `v6/axum-poc/` (compiles, running on port 8002)
- **FastAPI**: Running on port 8001 (do NOT stop it)
- **LocalTunnel**: aria-backend.loca.lt (maps to 8001)
- **USB-ARIA Agent**: `usb-aria/aria_usb_agent.py` (created but awaiting your daemon endpoints)
- **Discord**: Use existing webhook

## What's Already Done
1. ✅ Axum POC compiles and runs on port 8002
2. ✅ 18 route modules (core, chat, skills, agents, memory, voice, vision, system, files, web, proactive, evolution, learning, computer, github, social, auth, admin, self_improvement, daemon)
3. ✅ Daemon endpoints: /api/pc/state, /api/daemon/task, /api/daemon/result, /api/daemon/heartbeat
4. ✅ USB-ARIA agent created at usb-aria/aria_usb_agent.py

## Your Next Tasks (Priority Order)
1. **Add SQLite integration** - Connect Axum to aura.db (C:\Users\User\Downloads\AURA\aura.db)
   - Add `rusqlite = { version = "0.31", features = ["bundled"] }` to Cargo.toml
   - Create `memory.rs` integration with existing SQLite tables

2. **Add Ollama chat via reqwest** - Make /api/chat call Ollama
   - Add `reqwest = { version = "0.11", features = ["json"] }` to Cargo.toml
   - Call http://localhost:11434/api/generate in chat handler

3. **Add task submission endpoint** - Let ARIA backend submit tasks to USB agents
   - POST /api/daemon/task with action="submit"
   - Accept task JSON, queue it for USB-ARIA pickup

4. **Add system metrics** - Populate /api/system/status with real data
   - CPU usage, RAM, disk space
   - Use sysinfo crate or shell commands

5. **Update USB-ARIA agent** to use Axum endpoints when fully ready

## Code Conventions
- Keep code clean (no comments unless needed)
- Use `serde_json` for JSON
- State management via `OnceLock` (static globals in Rust)
- Run on port 8002 to avoid conflict

## Coordination
- USB-ARIA agent polls these endpoints every 30s
- When you add real data to /api/pc/state, USB-ARIA will react
- Discord reporting: same webhook URL
- Post progress to Discord #aria-status

## Commands
```bash
# Build
cd v6/axum-poc
cargo build

# Run
cargo run
# Or: target\debug\aria-axum-poc.exe

# Test
curl http://127.0.0.1:8002/health
curl -X POST http://127.0.0.1:8002/api/pc/state -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:8002/api/daemon/heartbeat -H "Content-Type: application/json" -d '{"agent_id":"test"}'

# Format & Lint
cargo fmt
cargo clippy 2>&1 | grep warning
```

## FastAPI Routes to Migrate (Critical First)
From C:\Users\User\Downloads\AURA\ARIA_APP\backend\app.py (~312 routes total):
- /health ✅
- /api/chat (uses Ollama via ai_providers)
- /api/system/status ✅
- /api/tools/execute
- /api/skills/* (25 skills)
- /api/memory/* (long-term, short-term, working)
- /api/research/*
- /api/pc/state (NEW - for USB-ARIA)
- /api/daemon/* (NEW - for USB-ARIA)
- /api/github/webhook
- /api/voice/stt, /api/voice/tts

## DO NOT:
- Stop the FastAPI backend on port 8001
- Change the default branch
- Commit code (wait for instructions)

## DO:
- Add features incrementally
- Test each endpoint with curl
- Report progress to Discord
- Coordinate with USB-ARIA agent requirements

Start with SQLite integration, then Ollama chat.