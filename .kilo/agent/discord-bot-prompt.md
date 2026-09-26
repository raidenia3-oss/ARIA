# AURA Multi-Language Expansion — Agent Prompt

## Context
AURA is expanding beyond Python/TypeScript. We are adding Ruby, Go, Rust, and creative interfaces. Telegram and Termux are being removed. Discord is now the primary interaction channel.

## Current State
- Repository structure scaffolded under: `services/`, `interfaces/`, `tools/`, `docker/`
- Discord bot skeleton exists at: `services/discord-bot/`
- Gesture control skeleton at: `interfaces/gesture-control/`
- Voice commands skeleton at: `interfaces/voice-commands/`
- DSL compiler skeleton at: `tools/dsl-compiler/`
- Docker Compose multi-service file at: `docker/docker-compose.multi.yml`

## Your Mission
Advance the Discord bot from skeleton to production-ready, and prepare the ground for the next phases.

## Specific Tasks

### Task 1: Complete Discord Bot Connection
File: `services/discord-bot/bot.rb`

Requirements:
- The bot must connect to Discord using discordrb 3.4+
- Implement these slash commands with real behavior:
  - `/status` — call `AURA_BACKEND_URL/api/status` and return JSON
  - `/logs` — call `AURA_BACKEND_URL/api/logs?service=X&lines=Y` and return last N lines
  - `/restart` — call `AURA_BACKEND_URL/api/restart` with service name
  - `/deploy` — call `AURA_BACKEND_URL/api/deploy` with service name
  - `/esoteric` — return a fun esoteric code challenge (brainfuck, LOLCODE, etc.)
  - `/rules` — list or evaluate automation rules from Redis
- Add event listeners:
  - `ready` — log bot username and post to `#ops` channel
  - `message_create` — publish message events to Redis `aura:events`
  - `voice_state_update` — publish voice events to Redis `aura:events`
- Add error handling and reconnection logic
- Add unit tests in `services/discord-bot/spec/`

### Task 2: Docker & Local Run
- Update `services/discord-bot/Dockerfile` if needed
- Ensure `docker-compose -f docker/docker-compose.multi.yml up discord-bot` works
- Add a `docker-compose.override.yml` for local development with volume mounts
- Document exact steps to run locally in `services/discord-bot/README.md`

### Task 3: Backend API Stubs (if missing)
Check if these endpoints exist in the backend. If not, create minimal stubs:
- `GET /api/status` — returns JSON with service statuses
- `GET /api/logs` — returns { service, logs }
- `POST /api/restart` — returns { message }
- `POST /api/deploy` — returns { message }

Where to add them: `backend/main.py` or `backend/app/api/status/route.py` style.

### Task 4: Test Everything
- Run Ruby tests: `cd services/discord-bot && bundle exec rspec`
- Run Python tests: `pytest tests/unit/`
- Verify Docker Compose starts without errors
- Create a simple integration test script that:
  1. Starts Redis
  2. Starts the bot
  3. Simulates a slash command call
  4. Verifies the response

### Task 5: Documentation
- Update `docs/multilanguage-structure.md` with the current state
- Add a `services/discord-bot/CHANGELOG.md` with what was done
- Ensure all READMEs have accurate setup instructions

## Constraints
- Do NOT modify `packages/frontend/`, `packages/backend/`, `packages/hf-space/` unless absolutely necessary
- Keep all new code in the new structure: `services/`, `interfaces/`, `tools/`
- Use existing patterns from the codebase (FastAPI, Next.js, etc.)
- All tests must pass before finishing
- Do not hardcode secrets; use environment variables

## Deliverables
1. Working Discord bot connected to a real Discord server
2. All 6 slash commands functional
3. Redis event publishing working
4. Docker Compose multi-service stack running
5. Tests passing (Ruby + Python)
6. Updated documentation

## How to Verify
```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start backend (if not running)
cd packages/backend
uvicorn main:app --reload

# Terminal 3: Start Discord bot
cd services/discord-bot
ruby bot.rb

# Terminal 4: Run tests
pytest tests/unit/
cd services/discord-bot && bundle exec rspec
```

## Discord Developer Portal Checklist
- [ ] Bot created at https://discord.com/developers/applications
- [ ] Token copied to `.env.local`
- [ ] Client ID copied to `.env.local`
- [ ] Guild ID copied to `.env.local`
- [ ] Bot invited to server with `bot` and `applications.commands` scopes
- [ ] Message Content Intent enabled
- [ ] Server ID, Channel ID noted for `#ops`

## Next Phase Preview (after this)
- Gesture control integration with Discord bot
- DSL compiler for Ruby rules
- Esoteric lab playground
- Training engine in Rust

Start now. Prioritize Task 1 (bot connection) and Task 3 (backend stubs) first.
