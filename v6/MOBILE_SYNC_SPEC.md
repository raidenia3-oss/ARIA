# ARIA v6.0 — Phase Airi (Mobile Sync) Specification

Status: Draft / Phase Airi
Backend: `v6/axum-poc` (Rust + Axum), bound to `127.0.0.1:8002`
Client: `v6/airi_mobile` (Flutter 3.x)
Source of truth: `v6/axum-poc/src/{state.rs,daemon.rs,core.rs,system.rs,computer.rs,auth.rs,agents.rs,skills.rs,chat.rs}`

---

## 0. Current backend reality vs. target protocol

This section is normative. Everything the mobile client does today is written against the
**current** backend; everything in §3–§5 is the **target** protocol that the backend must
implement before production mobile sync.

### 0.1 What the backend implements today

| Concern | Reality | Source |
| --- | --- | --- |
| WebSocket | `GET /ws` is an **echo loop**. Sends one `connected` welcome, echoes every text frame as `{"type":"echo",...}`, answers binary with `{"type":"ack"}`, relays `Ping`→`Pong`. | `state.rs:14-69` |
| Auth | None. `CorsLayer::permissive()`, no auth middleware layer. `/api/auth/login` returns a **hardcoded placeholder token** `"axum-jwt-token-placeholder"`. | `auth.rs:30-45`, `lib.rs:68-72` |
| Rate limiting | None. | `lib.rs:44-73` |
| Push | None. | — |
| Task queue | `VecDeque<Value>` in `SharedState` (`state.rs:79`). Nothing currently enqueues into it. | `daemon.rs:127` |
| Daemon protocol | Functional: `get_pending`, `report_status`, `report_result`, `heartbeat`. | `daemon.rs:140-279` |
| PC state | `POST /api/pc/state` returns a **hardcoded stub** (`active: true`, `idle_seconds: 0`, `session_user: "ARIA-USB"`). Request body is discarded. | `daemon.rs:109-121` |
| Memory / system info | Hardcoded constants (16 GB total, 50% used, 75 volume, fixed app list). | `system.rs`, `computer.rs` |
| CPU | **No CPU endpoint exists.** `/api/computer/status` returns `cpu: "x86_64"` (the architecture string), not a load percentage. | `computer.rs:112-120` |

### 0.2 Blocking backend defects found during this phase

1. **`daemon.rs` does not compile.** `HeartbeatResponse` is used at `daemon.rs:255` and
   `daemon.rs:275` but is never defined anywhere in `src/` (`grep HeartbeatResponse` → 2
   hits, both in `daemon.rs`). The struct must be added:
   ```rust
   #[derive(Serialize)]
   struct HeartbeatResponse {
       status: String,
       timestamp: u64,
   }
   ```
2. **No CPU telemetry endpoint.** Mobile dashboard cannot show CPU load until
   `GET /api/system/cpu` exists (see §4.3).
3. **No auth enforcement.** The mobile client sends `Authorization: Bearer <token>` from the
   moment it exists, but the server ignores it. This is fail-open and must be closed before
   the backend binds to a non-loopback interface.

### 0.3 Gaps the mobile client must bridge (client-side workarounds)

The Flutter client in this phase is written to be **forward compatible**:

- It parses the WS `echo` frame's `original` field and re-dispatches the inner JSON. Once the
  server emits typed frames (`task_available`, `pc_state_change`, …) the same parser handles
  them with no client change. See `lib/models/message.dart` → `Message.fromWire`.
- It derives "agents online" from `/api/agents/status`, since the server exposes no
  `daemon_agents` list endpoint.
- It treats `uptime_ms` from `/health` as the uptime source and refines it locally between
  polls (the counter is a snapshot, not a stream).
- It shows `CPU —` until §0.2.2 is resolved.

---

## 1. WebSocket connection flow

### 1.1 Transport

```
ws://<host>:8002/ws          (cleartext, loopback / LAN only)
wss://<host>:8443/ws         (TLS, required for anything beyond trusted LAN)
```

Axum's `WebSocketUpgrade` performs a standard RFC 6455 handshake. The client sends
`Sec-WebSocket-Protocol` only if a subprotocol is negotiated; the current server does not
negotiate one, so the client sends none.

### 1.2 Lifecycle state machine

```
        ┌──────────────┐
        │ disconnected  │◄──────────── close / fatal error
        └──────┬───────┘
               │ app start, settings change, or network regained
               ▼
        ┌──────────────┐   handshake fail    ┌─────────────┐
        │  connecting  ├───────────────────►│  backoff    │
        └──────┬───────┘                    └──────┬──────┘
               │ HTTP 101                        │ wait 1s,2s,4s…30s (jitter ±20%)
               ▼                                 └──► connecting
        ┌──────────────┐
        │  connected   │  ── welcome received ──► ready
        └──────┬───────┘
               │ heartbeat missed 2× (60s)
               ▼
        ┌──────────────┐
        │  degraded    │ ── ping OK ──► connected
        └──────────────┘
```

### 1.3 Connection sequence

1. **Resolve endpoint** from `SettingsService.baseUrl`
   (`http://host:8002` → `ws://host:8002/ws`; `https://…` → `wss://…/ws`).
2. **Attach credentials.** Query param `?token=<jwt>` **and** header
   `Authorization: Bearer <jwt>`. Browsers/WS clients that cannot set headers rely on the
   query param. Tokens live in the `airi_settings` Hive box; the server must accept either.
3. **Identify the client** with a first frame:
   ```json
   { "type": "identify", "client": "airi_mobile", "client_version": "0.1.0",
     "device_id": "<uuid v4 persisted in Hive>", "user_agent": "Flutter/iOS" }
   ```
4. **Server sends `connected`** (§3.1). This frame is the app's "backend is live" signal.
5. **Client subscribes to channels** (§2).
6. **Client starts ping loop** — a WebSocket control-frame `Ping` every 30 s. The server
   already relays `Ping`→`Pong` (`state.rs:53-55`), so this works with the POC unchanged.
7. **On reconnect**, the client re-runs steps 3–6 and then replays the offline queue (§5).

### 1.4 Backoff policy

| Attempt | Delay | Jitter |
| --- | --- | --- |
| 1 | 1 s | ±20% |
| 2 | 2 s | ±20% |
| 3 | 4 s | ±20% |
| 4 | 8 s | ±20% |
| 5+ | 30 s (capped) | ±20% |

Jitter is mandatory: multiple phones reconnecting after a router reboot otherwise stampede
the backend. Reset to attempt 1 after a connection has stayed up for 60 s.

### 1.5 Battery / lifecycle rules

- App backgrounded → **keep the socket open** (iOS `voip` background mode is out of scope for
  Phase Airi; on iOS the socket dies when suspended and reconnect is lazy).
- Screen locked > 5 min → drop the socket, switch to `GET /api/system/status` polling at
  60 s, and rely on FCM (§6) for anything urgent.
- Battery < 15% → force polling mode, disable the socket entirely.
- Every socket open/close is written to the `airi_log` Hive box for post-mortem debugging.

---

## 2. Channels and subscription

The target protocol adds channel multiplexing on the single `/ws` connection.

**Client → server, `subscribe`:**
```json
{ "type": "subscribe", "channels": ["system", "tasks", "agents", "alerts"] }
```

**Server → client, `subscribed` (one per batch):**
```json
{ "type": "subscribed", "channels": ["system", "tasks"], "server_time": 1756400000 }
```

| Channel | Pushes | Default |
| --- | --- | --- |
| `system` | `pc_state_change`, `system_alert` (cpu, memory, disk, backend down/up) | on |
| `tasks` | `task_available`, `task_result` | on |
| `agents` | `agent_status_change` (swarm + daemon agents) | on |
| `alerts` | `system_alert` only (deduplicated) | on |
| `orb` | `orb_phase` (`idle`/`thinking`/`responding`/`listening`/`wisdom`) | off |

`unsubscribe` takes the same `channels` array. An unknown channel name is ignored, not an
error — the server must tolerate newer clients asking for older servers' channel sets.

---

## 3. Message types

All frames are **UTF-8 JSON text**. The current server relays application-level `Ping`/
`Pong` control frames; those are transport-level and are **not** part of this envelope set.

### 3.1 Envelope

Every server → client frame has a `type` discriminator and an optional `ts` (unix seconds,
server clock):

```json
{ "type": "<discriminator>", "ts": 1756400000, "seq": 1042, "data": { } }
```

`seq` is a monotonically increasing per-connection counter. A client that sees a gap
(`seq` jumps by more than 1) must re-fetch full state over REST rather than assume the
intervening frames are irrelevant. The POC echo server does not send `seq`; clients must
treat it as optional.

### 3.2 `connected` — server → client, on connect

Emitted by the current server (`state.rs:22-26`):

```json
{
  "type": "connected",
  "message": "ARIA Axum WebSocket ready",
  "agents": ["CodeAnalyzer", "DocsWriter", "Tester", "ResearchAgent"],
  "server": "ARIA-Axum-8002",
  "version": "0.1.0-POC",
  "uptime_ms": 918273,
  "ts": 1756400000
}
```

`agents` is the swarm roster. It is **not** a live status list — the client must call
`GET /api/agents/status` for per-agent state.

### 3.3 `heartbeat` — server → client, every 15 s

```json
{ "type": "heartbeat", "ts": 1756400000, "data": {
    "uptime_ms": 918273,
    "requests_served": 412,
    "daemon_agents": 1,
    "pending_tasks": 0,
    "completed_results": 7
} }
```

Field names mirror `/api/system/status` (`core.rs:53-67`) so a single Dart model
(`SystemStatus`) decodes both. The client's independent 30 s control-frame `Ping` is a
transport keepalive; the server's 15 s `heartbeat` is a *data* keepalive. Both are needed:
the first detects a dead TCP socket, the second refreshes the UI without a REST round-trip.

### 3.4 `task_available` — server → client

Fired when `daemon_task_get` (`daemon.rs:123-138`) would report `available: true`.

```json
{ "type": "task_available", "ts": 1756400000, "data": {
    "id": "task-7f3a",
    "task_type": "system_scan",
    "payload": { "depth": "full" },
    "assigned_to": null,
    "status": "pending",
    "created_at": 1756400000
} }
```

Shape matches `struct Task` in `daemon.rs:22-30`. `task_type` is currently free-form; the
known vocabulary is `system_control`, `apps`, `screenshot`, `volume`, `lock`, `open`,
`chat`, `generic` (anything else decodes as `generic`, never throws).

### 3.5 `task_result` — server → client

Fired after `POST /api/daemon/result` records a result (`daemon.rs:217-250`).

```json
{ "type": "task_result", "ts": 1756400000, "data": {
    "task_id": "task-7f3a",
    "agent_id": "ARIA-USB",
    "status": "ok",
    "output": { "screenshots": 1 },
    "executed_at": "2026-09-28T21:44:11Z"
} }
```

Shape matches `struct TaskResult` in `daemon.rs:32-39`. `executed_at` is an ISO-8601
**string** (not epoch) — the client parses it as `DateTime`, and treats a parse failure as
`null` rather than crashing.

### 3.6 `pc_state_change` — server → client

Fired when the PC's activity state flips, or on the first poll after a change.

```json
{ "type": "pc_state_change", "ts": 1756400000, "data": {
    "active": true,
    "idle_seconds": 0,
    "session_user": "ARIA-USB",
    "timestamp": 1756400000
} }
```

Shape matches `struct PCStateResponse` in `daemon.rs:51-57`. **Caveat:** the current
handler returns hardcoded values and ignores the request body (`daemon.rs:109-121`). Until
that is fixed, the client treats this frame as a liveness signal only and never renders
`idle_seconds` as ground truth — it shows "state reporting is stubbed on this backend".

### 3.7 `system_alert` — server → client

```json
{ "type": "system_alert", "ts": 1756400000, "data": {
    "level": "warning",
    "code": "memory_high",
    "message": "RAM usage above 90%",
    "metric": { "name": "memory", "value": 91.4, "threshold": 90.0, "unit": "percent" },
    "actions": ["dismiss", "open_dashboard", "run_cleanup"]
} }
```

`level` ∈ `info` | `warning` | `critical`. `code` is a stable machine identifier (snake_case);
`message` is human-facing and **may be localized** — never key UI logic off it.

### 3.8 `echo` / `ack` — POC-era frames

```json
{ "type": "echo", "original": "<the exact text sent>", "server": "ARIA-Axum-8002" }
{ "type": "ack",  "status": "binary_received" }
```

`echo` is the only frame the current server produces. The client unwraps `original`, parses
it as JSON, and feeds the result back through the same dispatcher as a top-level frame. A
client sends nothing that is not valid JSON, so `original` always parses; if it does not,
the frame is logged and dropped.

### 3.9 Client → server frames

| `type` | Body | Notes |
| --- | --- | --- |
| `identify` | `client`, `client_version`, `device_id` | first frame after open |
| `subscribe` | `channels: string[]` | |
| `unsubscribe` | `channels: string[]` | |
| `ping` | — | app-level; distinct from the control-frame `Ping` |
| `command` | `command_type`, `params`, `idempotency_key` | preferred over REST for commands (§4.2) |
| `ack` | `ref: <seq or idempotency_key>` | optional delivery receipt |

`command` frames are only honoured by a server that advertises `"capabilities": ["command"]`
in its `connected` frame. Otherwise the client uses REST.

---

## 4. REST API surface for mobile

### 4.1 Connectivity and status (unauthenticated in POC)

| Method | Path | Returns | Mobile use |
| --- | --- | --- | --- |
| GET | `/health` | `{status, framework, version, uptime_ms}` | reachability probe, uptime |
| GET | `/api/system/status` | `{status, framework, version, uptime_ms, requests_served, chats_processed, daemon_agents, pending_tasks, completed_results, port, mode}` | dashboard primary poll |
| GET | `/api/system/ping` | `{status, latency_ms, server, framework}` | latency badge |
| GET | `/api/system/whois` | `{status, hostname, os, arch, framework}` | header device info |
| GET | `/api/system/time` | `{status, timestamp, server}` | clock skew check for `ts` fields |
| GET | `/api/system/memory` | `{status, total, used, available, usage_percent, server}` | memory gauge |
| GET | `/api/system/log` | `{status, entries[], server}` | mobile log view |
| GET | `/api/system/scan` | `{status, network{…}, server}` | reachability of sibling services |

### 4.2 Computer control (the Command screen)

All are `GET` in the current backend.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/computer/control` | generic system-control ping |
| GET | `/api/computer/apps` | `{running: string[]}` |
| GET | `/api/computer/screenshot` | returns a status stub; **no image payload yet** (§0.2) |
| GET | `/api/computer/volume` | `{volume, muted}` |
| GET | `/api/computer/lock` | locks the PC — confirm dialog required |
| POST | `/api/computer/open` | `{target: string}` |
| POST | `/api/computer/execute` | `{command: string}` — **dangerous; UI gates this** |
| GET | `/api/computer/processes` | `{processes: string[]}` |
| GET | `/api/computer/status` | `{cpu: "<arch>", os, memory}` — `cpu` is **not** a load value |

`/api/system/*` mirrors `/api/computer/*` (`system.rs` vs `computer.rs`) with identical
bodies. The mobile client uses `/api/computer/*` as canonical and falls back to
`/api/system/*` on 404, since one of the two module sets may be retired during migration.

### 4.3 Phase Airi backend additions (required, not yet implemented)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/system/cpu` | `{usage_percent, per_core[], temp_c, load_avg}` — unblocks the CPU tile |
| GET | `/api/system/disk` | `{total, used, available, usage_percent}` |
| GET | `/api/pc/state` | `GET` variant of the existing `POST` returning real idle time |
| GET | `/api/agents` | list with live `status` per agent (currently `/api/agents` is static) |
| GET | `/api/tasks/pending` | queue depth + next task, for polling fallback |
| POST | `/api/daemon/task` | already exists — mobile uses it as an agent would (§4.4) |

### 4.4 Daemon / agent protocol (mobile acting as a USB-ARIA node)

The mobile client can register itself as a daemon agent. Endpoints are already implemented
in `daemon.rs`.

**Register / keepalive**
```
POST /api/daemon/heartbeat
{ "agent_id": "airi_mobile-<device_id>", "status": "alive" }
→ { "status": "alive", "timestamp": 1756400000 }
```
Send every 30 s. The server upserts into `SharedState.daemon_agents`
(`daemon.rs:252-279`), which is what `/api/agents/status` reads
(`agents.rs:58-67`) — this is how the phone becomes visible on the dashboard.

**Claim work**
```
POST /api/daemon/task
{ "agent_id": "airi_mobile-<device_id>", "action": "get_pending" }
→ { "available": true,
    "task": { "id", "task_type", "payload", "assigned_to", "status", "created_at" },
    "status": "task_assigned" }
```
`get_pending` atomically flips the task to `assigned` and stamps `assigned_to`
(`daemon.rs:157-180`). **Claiming is not optional** — polling `GET /api/daemon/task`
(`daemon.rs:123-138`) never assigns, so a mobile client using GET would loop forever on the
same pending task.

**Report status**
```
POST /api/daemon/task  { "agent_id": "...", "action": "report_status", "status": "busy" }
→ { "available": false, "task": null, "status": "status_reported" }
```

**Report result**
```
POST /api/daemon/result
{ "agent_id": "...",
  "result": { "task_id", "status", "output", "executed_at" } }
→ { "status": "result_recorded", "total_results": 8 }
```
`result_recorded` does **not** emit a `task_result` WS frame in the current build; the
mobile client that submitted the task must reconcile via `GET /api/system/status`
(`completed_results` delta) until the WS broadcast lands.

**Publish PC state** (from the phone, about the phone — not the PC)
```
POST /api/pc/state { "agent_id": "...", "pc_state": { ... } }
→ { "active", "idle_seconds", "session_user", "timestamp" }
```

**Unknown `action`** returns `{available:false, status:"unknown_action"}` — a soft failure.
The client treats it as a protocol mismatch, logs it, and falls back to GET polling.

### 4.5 Chat and agents

| Method | Path | Body / Notes |
| --- | --- | --- |
| POST | `/api/chat` | `{message, session_id?, provider?}` → `{response, provider, latency_ms, session_id}` |
| POST | `/api/chat/stream` | same shape, **not actually streamed** (`chat.rs:108-126`) |
| GET | `/api/chat/history` | `{history: [], session_id: "default"}` — always empty in POC |
| GET | `/api/agents/status` | `{name, agent_count, agents[{name, role, status, task_count, error_count}]}` |
| POST | `/api/agents/execute` | `{agent, task}` |
| POST | `/api/agents/research` | `{query}` |
| GET | `/api/agents/harness/skills` | skill names |
| GET | `/api/skills` | `{skills: [{name, description, status}], count}` |
| POST | `/api/skills/run` | `{skill}` |

`/api/chat` proxies Ollama with a 60 s timeout (`chat.rs:84`). The mobile client must use a
client timeout > 60 s (default 70 s) or it will abort before the backend does.

### 4.6 Auth

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/auth/login` | `{username}` → `{status, username, token, server}` — token is a **placeholder** |
| POST | `/api/auth/refresh` | → `{status, token, server}` |
| GET | `/api/auth/validate` | → `{status, valid}` |
| GET | `/api/auth/profile` | → `{user, role}` |
| GET | `/api/auth/permissions` | → `{permissions: ["read","write","execute","admin"]}` |
| GET | `/api/auth/sessions` | → `{sessions: []}` |

The client stores the token in the `airi_settings` Hive box and sends
`Authorization: Bearer <token>` on every request plus `?token=` on the WS URL. Because the
POC does not validate it, the client shows a clear **"backend is not enforcing auth"**
warning in Settings until a real JWT middleware exists.

### 4.7 Rate limits

**No rate limiting is implemented.** The client enforces a local budget so it is a good
citizen and is not the thing that breaks when the server adds limits:

| Class | Budget | Behaviour on breach |
| --- | --- | --- |
| `poll` (status, memory, agents) | 1 per 5 s, burst 3 | coalesce — drop the tick |
| `command` (control, lock, volume, open, screenshot) | 1 per 2 s, burst 5 | queue locally (§5) |
| `execute` (`/api/computer/execute`) | 1 per 30 s | hard block with a countdown |
| `chat` | 1 per 10 s | queue |
| `daemon` (heartbeat/task/result) | 1 per 30 s | drop, never queue |
| `login` | 5 per 15 min | hard block |

The server-side limits this client is written to tolerate: 60 req/min per client for
`poll`, 30 req/min for `command`, 10/min for `execute`, 429 with
`Retry-After: <seconds>` on breach, and `401` with `{"error":"token_expired"}` on a stale
token. The client honours `Retry-After` verbatim.

### 4.8 Error contract

Target shape — the current handlers return HTTP 200 with an in-body status string
(`{"status":"error","error":"..."}`), e.g. `daemon.rs:247`. The client decodes **both**:

```json
{ "error": { "code": "unknown_action", "message": "…", "retryable": false },
  "status": "error" }
```

| Code | HTTP | Retryable |
| --- | --- | --- |
| `unauthorized` / `token_expired` | 401 | after refresh |
| `forbidden` | 403 | no |
| `rate_limited` | 429 | yes, after `Retry-After` |
| `backend_offline` | — (transport) | yes, backoff |
| `unknown_action` | 200 | no — protocol mismatch |
| `internal` | 5xx | yes, exponential |

The client never throws on a body-level `status: "error"`; it returns a typed
`BackendResult.err`.

---

## 5. Offline-first sync strategy

### 5.1 Principles

1. **The phone is the source of truth for user intent, the server for PC state.** Commands
   are never lost; state is never invented.
2. **Every mutating command is queued locally first, sent second.** The UI acknowledges
   instantly on enqueue, not on server ACK. Latency from the network must not gate the user.
3. **Idempotency is mandatory.** `POST /api/computer/open` twice is harmless, but a
   retried `chat` or `execute` is not. Every queued command carries a client-generated
   `idempotency_key` (UUID v4) and the client will not re-send a command after a
   non-idempotent server response (§5.4).
4. **State is last-known-good, timestamped.** Snapshots are cached in Hive with the
   server's `ts`. The UI always renders the cache first, then upgrades to live. It must
   never render a spinner over stale data it already has.

### 5.2 Queue model

Hive box `airi_offline_queue`, entries of type `QueuedCommand`:

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | String (UUID v4) | primary key |
| `idempotencyKey` | String | sent as a header; dedupes retries |
| `kind` | enum | `control`, `open`, `screenshot`, `volume`, `lock`, `chat`, `execute`, `daemon` |
| `path` | String | e.g. `/api/computer/lock` |
| `method` | String | `GET` / `POST` |
| `body` | Map? | request payload |
| `createdAt` | int (epoch ms) | FIFO ordering, TTL |
| `attempts` | int | retry accounting |
| `lastError` | String? | surfaced in the Command screen |
| `state` | enum | `pending`, `inflight`, `done`, `failed` |

FIFO by `createdAt`. `state == inflight` on app start is reset to `pending` — a crash
mid-flight must not strand a command.

### 5.3 Replay algorithm

Triggered by: WS `connected` frame, or a successful poll after ≥ 60 s of being offline,
or manual "Retry now" in the Command screen.

```
replay():
  for cmd in queue.pending.orderBy(createdAt):
      if cmd.createdAt older than 24h:  cmd.state = failed; cmd.lastError = "expired"; continue
      cmd.state = inflight; persist
      try:
          res = send(cmd)
          if res.httpStatus in 200..299 and res.body.status != "error":
              cmd.state = done;  delete
          elif res.httpStatus == 429:
              cmd.state = pending
              sleep(max(Retry-After, 30s))     # stop the loop, resume later
          elif res.httpStatus == 401:
              cmd.state = pending; refresh token; break
          else:
              cmd.attempts += 1
              cmd.state = cmd.attempts >= 5 ? failed : pending
              if failed: break                  # do not replay past a hard failure
      catch transport error:
          cmd.attempts += 1
          cmd.state = pending; break           # network still down, stop
```

Replay is **serial**, never parallel: the daemon queue is order-sensitive, and a
half-delivered sequence of `lock` / `unlock` is worse than a late one.

### 5.4 Ordering guarantees

- `lock` and `open` are **stateful** — they must not be reordered. FIFO plus serial replay
  covers this.
- `screenshot` and `execute` are **idempotent-unsafe by cost** (each triggers real work on
  the PC). After one `attempts == 1` failure they go straight to `failed` and require manual
  retry from the UI.
- `daemon` commands (`heartbeat`, `get_pending`, `report_result`) are **never queued** —
  a stale heartbeat is worse than none, and `report_result` for a task that has since been
  reassigned is actively harmful. They are dropped and the task is re-registered instead.

### 5.5 Cache

Hive box `airi_cache`:

| Key | TTL | Refresh |
| --- | --- | --- |
| `system_status` | 10 s | poll + WS `heartbeat` |
| `memory` | 10 s | poll |
| `cpu` | 10 s | poll (stub until `/api/system/cpu` exists) |
| `agents` | 30 s | poll + WS `agents` channel |
| `whois` | 1 h | poll |
| `chat_history` | 1 h | poll |
| `tasks` | 60 s | WS `tasks` channel + `GET /api/daemon/task` fallback |

`whois` and `chat_history` are effectively static in the POC and are cached indefinitely
in practice.

### 5.6 Conflict resolution

There is no multi-writer conflict on PC state — the phone never writes the PC's state, and
the PC never writes the phone's queue. The only overlap is the task assignment
(`assigned_to` in `daemon.rs:157-180`): if the WS pushes `task_available` for a task the
phone already claimed and completed, the server's assignment wins and the client discards
its local copy of that task's state, keeping only the result.

---

## 6. Push notification payload

### 6.1 Transport

FCM data messages (not notification messages) so the client controls presentation and can
decide locally whether to show a banner. High-priority Android channel `aria_alerts`.
FCM is not yet wired in the backend — this section is the contract the backend must
implement.

### 6.2 Payload

```json
{
  "collapse_key": "aria.memory_high",
  "priority": "high",
  "ttl": 3600,
  "data": {
    "type": "system_alert",
    "alert_level": "warning",
    "alert_code": "memory_high",
    "title": "ARIA — RAM alta",
    "body": "Uso de memoria por encima del 90%",
    "ts": "2026-09-28T21:44:11Z",
    "metrics": { "usage_percent": 91.4, "threshold": 90.0 },
    "deep_link": "airi://dashboard/system",
    "server": "ARIA-Axum-8002"
  }
}
```

| Key | Required | Notes |
| --- | --- | --- |
| `type` | yes | mirrors the WS discriminator (§3.1) |
| `alert_level` | yes | `info` \| `warning` \| `critical` |
| `alert_code` | yes | stable snake_case identifier |
| `title` / `body` | yes | already localized by the server; the client does **not** re-localize |
| `ts` | yes | ISO-8601 UTC |
| `metrics` | no | flat JSON, numbers only |
| `deep_link` | no | `airi://<screen>`; unknown screens open the dashboard |
| `server` | yes | instance id, for multi-host setups |

### 6.3 Push ↔ WS mapping

| Push `type` | Equivalent WS frame | Trigger |
| --- | --- | --- |
| `system_alert` | `system_alert` | threshold breach |
| `task_available` | `task_available` | queued work for this phone |
| `task_result` | `task_result` | daemon finished |
| `pc_state_change` | `pc_state_change` | PC went idle / woke |
| `backend_down` | — | health probe failed 3× (30 s) |
| `backend_up` | `connected` | health probe recovered |

### 6.4 Client handling

1. **Connected** → `flutter_local_notifications` shows the notification; no WS action.
2. **Backgrounded** → FCM `onBackgroundMessage` handler writes to the `airi_log` Hive box
   and posts a local notification. `task_available` is the only type that wakes the app.
3. **Tap** → route by `deep_link`; the app connects, replays the queue (§5.3), then
   navigates.
4. **Deduplication** — the same `alert_code` is not shown twice within 60 s. Tracked in
   the `airi_log` Hive box. `collapse_key` handles server-side collapsing, but a phone that
   was offline accumulates messages locally and must dedupe on receipt.
5. **User controls** — four independent switches in Settings: `taskAvailable`,
   `taskResult`, `systemAlert`, `pcStateChange`. All default **on** except `pcStateChange`,
   which defaults **off** (highest noise, lowest urgency).

---

## 7. Security

| Concern | Control |
| --- | --- |
| Transport | Loopback/LAN only in Phase Airi. Any remote host **must** be `https`/`wss`. The client refuses plaintext to a non-loopback host unless the user explicitly overrides in Settings. |
| Token storage | Hive, unencrypted, in the app sandbox. Acceptable for a debug build; a release build needs `flutter_secure_storage`. |
| PIN / biometric | out of scope |
| Dangerous commands | `execute` and `lock` require an in-app confirmation dialog. `execute` is additionally rate-limited to 1/30 s. |
| Command allowlist | the Command screen only offers the kinds in §5.4; no arbitrary-path requests from the UI. |
| Logs | command bodies may contain user text; the log box is capped at 500 entries and truncates bodies to 200 chars. |
| CORS | `CorsLayer::permissive()` (`lib.rs:72`) is acceptable for a loopback-bound POC and must be replaced with an explicit origin list before LAN exposure. |

---

## 8. Implementation status

| Item | Status |
| --- | --- |
| `v6/MOBILE_SYNC_SPEC.md` | this document |
| `v6/airi_mobile/pubspec.yaml` | created |
| `v6/airi_mobile/lib/main.dart` | created |
| `v6/airi_mobile/lib/models/{pc_state,task,message}.dart` | created |
| `v6/airi_mobile/lib/services/{backend_service,offline_queue,settings_service,notification_service}.dart` | created |
| `v6/airi_mobile/lib/screens/{dashboard,command,settings}.dart` | created |
| Flutter SDK | **not installed** — source only |
| `HeartbeatResponse` compile fix (`daemon.rs`) | **outstanding backend blocker** |
| Real auth middleware | outstanding |
| Rate limiting (server) | outstanding |
| `GET /api/system/cpu` | outstanding |
| Real `POST /api/pc/state` | outstanding |
| WS broadcast of `task_available` / `task_result` | outstanding |
| FCM sender | outstanding |
| Screenshot image payload | outstanding |

### Dependency note

`pubspec.yaml` uses **`web_socket_channel`**, not `websocket_client`. The latter is
deprecated and unmaintained (last release 2018) and does not support the RFC 6455
control-frame ping the reconnect logic in §1.4 depends on. `web_socket_channel` is its
maintained successor with the same `WebSocketChannel` API surface.
