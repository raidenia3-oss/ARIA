# ARIA v6.0 — Phase Airi (Mobile Sync) Specification

Status: Draft / Phase Airi — **verified against source on 2026-09-29**
Backend: `v6/axum-poc` (Rust + Axum), bound to `127.0.0.1:8002` by default.
  Override with `ARIA_BIND` (e.g. `ARIA_BIND=0.0.0.0:8002`) to reach it from a
  physical device on the LAN; see `v6/airi_mobile/README.md` for the security note.
Client: `v6/airi_mobile` (Flutter 3.x)
Source of truth: `v6/axum-poc/src/{state.rs,daemon.rs,core.rs,system.rs,computer.rs,auth.rs,agents.rs,skills.rs,chat.rs,lib.rs}`

> **Auth is enforced and rate limiting is live.** Earlier revisions of this document
> described both as absent and flagged a non-compiling `daemon.rs`. All three statements
> were stale — the fixes landed before this pass. See §0.1–§0.2 for the corrected
> picture and for the defects that are *actually* still open.

---

## 0. Current backend reality vs. target protocol

This section is normative. Everything the mobile client does today is written against the
**current** backend; everything in §3–§5 is the **target** protocol that the backend must
implement before production mobile sync.

### 0.1 What the backend implements today

| Concern | Reality | Source |
| --- | --- | --- |
| WebSocket | `GET /ws` is an **echo loop**. Sends one `connected` welcome, echoes every text frame as `{"type":"echo",...}`, answers binary with `{"type":"ack"}`, relays `Ping`→`Pong`. | `state.rs:160-211` |
| Auth | **Enforced.** The `auth::guard` middleware runs on every path and requires a bearer token on all non-public routes. Key comes from `ARIA_API_KEY`; a random key is generated and printed if that variable is unset. Comparison is constant time. | `auth.rs:214-287`, `state.rs:47-88` |
| Public paths | `/`, `/health`, `/ws`, `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh` — the rest require a token. | `auth.rs:35-45` |
| Token transports | `Authorization: Bearer <t>` **or** `X-API-Key: <t>`. A `?token=` query param is **not** read by the server. | `auth.rs:161-176` |
| Rate limiting | **Implemented.** Fixed window, 100 requests / 60 s per client IP, on every path including public ones. Returns `429` + `Retry-After`, and stamps `X-RateLimit-Limit` / `X-RateLimit-Remaining` on every response. | `state.rs:20-22, 125-153`, `auth.rs:125-132, 290-296` |
| Push | None. | — |
| Task queue | `VecDeque<Value>` in `SharedState` (`state.rs:256`). Read by `daemon.rs:132,155` and `core.rs:50`; **nothing ever pushes onto it.** | `daemon.rs:128-143` |
| Daemon protocol | Functional: `get_pending`, `report_status`, `report_result`, `heartbeat`. | `daemon.rs:140-284` |
| PC state | `POST /api/pc/state` returns a **hardcoded stub** (`active: true`, `idle_seconds: 0`, `session_user: "ARIA-USB"`). Request body is discarded. | `daemon.rs:114-126` |
| Memory / system info | `/api/computer/*` — **RESOLVED.** No fabricated constants left: unmeasured data is served as `data_source: "unavailable"` with explicit `null`s (§4.2). `/api/system/*` mirrors have their own bodies and are tracked separately. | `computer.rs`, `system.rs` |
| CPU | **No CPU endpoint exists.** `/api/computer/status` no longer publishes a `cpu` key at all — it used to carry the architecture string, which the client read as a load percentage. | `computer.rs`, `system.rs` |
| Orb state | `/api/orb/{state,phase,start,stop}` exist and control the native wgpu orb window. Not mobile-relevant yet, but a second WS client can read it. | `daemon.rs:101-104, 286-349` |

### 0.2 Blocking backend defects found during this phase

> **Status as of 2026-09-29: items 1 and 3 are RESOLVED — the spec previously reported
> them as outstanding. Verified against the tree and against a successful
> `cargo build --release` (`target/release/aria-axum-poc.exe`, built after both
> fixes landed).**

1. ~~**`daemon.rs` does not compile.** `HeartbeatResponse` is used at `daemon.rs:255`
   and `daemon.rs:275` but is never defined.~~ **RESOLVED** — the struct is defined at
   `daemon.rs:78-82`:
   ```rust
   #[derive(Serialize)]
   struct HeartbeatResponse {
       status: String,
       timestamp: u64,
   }
   ```
2. **No CPU telemetry endpoint.** Mobile dashboard cannot show CPU load until
   `GET /api/system/cpu` exists (see §4.3). *Still outstanding.*
3. ~~**No auth enforcement.**~~ **RESOLVED** — `auth::guard` is layered in
   `create_full_router` (`lib.rs:96-99`) and rejects unauthenticated requests on every
   non-public path with `401 {"error":"unauthorized","status":401}` plus
   `WWW-Authenticate: Bearer realm="aria"`. *Still outstanding, by design:*
4. **`/api/auth/login` mints a useless token.** It still returns the hardcoded
   literal `"axum-jwt-token-placeholder"` (`auth.rs:312-327`) instead of the real
   `ARIA_API_KEY`. A client that follows the documented "POST /api/auth/login, store
   the token" flow will get a token the server rejects. The client must **not** rely
   on login; the operator supplies the key out of band and the user pastes it into
   Settings. Same for `POST /api/auth/refresh`, which returns
   `"axum-jwt-refreshed-token"` (`auth.rs:354-360`) — the client cannot refresh and
   must treat a `401` as "re-prompt for the key", not "refresh and retry".
5. **`/ws` is completely unauthenticated.** It is in `PUBLIC_PATHS` and the handler
   never calls `verify_token`, so a `?token=` on the WS URL is ignored and any LAN host
   can drive the echo loop. Acceptable while loopback-only; must be closed before LAN
   exposure.


### 0.3 Gaps the mobile client must bridge (client-side workarounds)

The Flutter client in this phase is written to be **forward compatible**:

- It parses the WS `echo` frame's `original` field and re-dispatches the inner JSON. Once the
  server emits typed frames (`task_available`, `pc_state_change`, …) the same parser handles
  them with no client change. See `lib/models/message.dart` → `Message.fromWire`.
- It derives "agents online" from `/api/agents/status`, since the server exposes no
  `daemon_agents` list endpoint. Daemon agents do appear there, appended to the four static
  swarm agents with `role: "USB-ARIA Daemon"` (`agents.rs:58-67`).
- It treats `uptime_ms` from `/health` as the uptime source and refines it locally between
  polls (the counter is a snapshot, not a stream).
- It shows `CPU —` until §0.2.2 is resolved.
- It falls back to `X-API-Key` when it cannot attach an `Authorization` header, and treats a
  `401` as fatal — there is no working refresh (§0.2.4).

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
2. **Attach credentials to REST only.** For HTTP the client sends
   `Authorization: Bearer <jwt>` (fallback `X-API-Key: <jwt>`). For the socket it appends
   `?token=<jwt>` purely as a future-proofing measure — **the current server ignores it**
   (`/ws` is in `PUBLIC_PATHS` and the handler never calls `verify_token`; see §0.2.5).
   Tokens live in the `airi_settings` Hive box. Once auth covers `/ws`, the server will
   read the same query param and no client change is required.
3. **Identify the client** with a first frame:
   ```json
   { "type": "identify", "client": "airi_mobile", "client_version": "0.1.0",
     "device_id": "<uuid v4 persisted in Hive>", "user_agent": "Flutter/iOS" }
   ```
   The current server treats this as an ordinary frame and echoes it back (§3.8).
4. **Server sends `connected`** (§3.2). This frame is the app's "backend is live" signal.
5. **Client subscribes to channels** (§2).
6. **Client starts ping loop** — a WebSocket control-frame `Ping` every 30 s. The server
   already relays `Ping`→`Pong` (`state.rs:195-199`), so this works with the POC unchanged.
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

Emitted by the current server (`state.rs:164-168`). **The frame carries only three keys** —
`server`, `version`, `uptime_ms` and `ts` are *not* sent and the client must not wait for
them:

```json
{
  "type": "connected",
  "message": "ARIA Axum WebSocket ready",
  "agents": ["CodeAnalyzer", "DocsWriter", "Tester", "ResearchAgent"]
}
```

Until the backend enriches this frame, the client fills the gaps from `GET /health`
(`version`, `uptime_ms`) and stamps `ts` locally from the phone clock.

`agents` is the swarm roster. It is **not** a live status list — the client must call
`GET /api/agents/status` for per-agent state. The frame also carries no `capabilities` key,
so per §3.9 `command` frames are unavailable and the client uses REST.

### 3.3 `heartbeat` — server → client, every 15 s (TARGET — not yet emitted)

```json
{ "type": "heartbeat", "ts": 1756400000, "data": {
    "uptime_ms": 918273,
    "requests_served": 412,
    "daemon_agents": 1,
    "pending_tasks": 0,
    "completed_results": 7
} }
```

Field names mirror `/api/system/status` (`core.rs:54-70`) so a single Dart model
(`SystemStatus`) decodes both. The REST route also returns `memory_safety`, `gc_pauses`,
`auth_failures`, `security` and `mode`; the WS frame is a subset and the model must tolerate
their absence. The client's independent 30 s control-frame `Ping` is a
transport keepalive; the server's 15 s `heartbeat` is a *data* keepalive. Both are needed:
the first detects a dead TCP socket, the second refreshes the UI without a REST round-trip.
Until the frame ships, the client gets the same data from a 5 s `GET /api/system/status`.

### 3.4 `task_available` — server → client

Fired when `daemon_task_get` (`daemon.rs:128-143`) would report `available: true`.

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

Fired after `POST /api/daemon/result` records a result (`daemon.rs:222-255`).

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
handler returns hardcoded values and ignores the request body (`daemon.rs:114-126`). Until
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

### 4.1 Connectivity and status

**Every route in this table except `/health` requires a bearer token** (§0.1). A missing or
wrong token is `401` before the handler runs.

| Method | Path | Returns | Mobile use |
| --- | --- | --- | --- |
| GET | `/health` | `{status, framework, version, uptime_ms}` — **public, no token** | reachability probe, uptime, `version` for the `connected` frame |
| GET | `/api/system/status` | `{status, framework, version, uptime_ms, memory_safety, gc_pauses, requests_served, chats_processed, daemon_agents, pending_tasks, completed_results, auth_failures, security{scheme, env_var, key_source, rate_limit_per_minute}, port, mode}` | dashboard primary poll |
| GET | `/api/system/health` | same as `/health` | alias |
| GET | `/api/system/ping` | `{status, latency_ms, server, framework}` | latency badge |
| GET | `/api/system/whois` | `{status, hostname, os, arch, framework}` | header device info |
| GET | `/api/system/time` | `{status, timestamp, server}` | clock skew check for `ts` fields |
| GET | `/api/system/memory` | `{status, total, used, available, usage_percent, server}` | memory gauge |
| GET | `/api/system/log` | `{status, entries[], server}` | mobile log view |
| GET | `/api/system/scan` | `{status, network{interfaces, ip, port_8002, port_8001}, server}` | reachability of sibling services |
| GET | `/api/system/control` \| `/volume` \| `/lock` \| `/apps` \| `/screenshot` \| `/open` | status stubs / constants | see §4.2 |
| GET | `/api/system/explorer` \| `/code_exec` | status stubs | desktop-only, not surfaced on mobile |

`daemon_agents` and `pending_tasks` in `/api/system/status` are `len()` of the live maps, so
`pending_tasks` counts **all** queued tasks regardless of status, not just `pending` ones.
Do not present it as a "ready work" count.

### 4.2 Computer control (the Command screen)

Not all GET — `/api/computer/open` and `/api/computer/execute` are `POST`.

**Contract for every `/api/computer/*` route.** Each one is exactly one of:
a `501` with `not_implemented` (the route advertises an action and this build performs none of it),
a `200` carrying `data_source: "unavailable"` plus explicit `null`s (the datum was never measured),
or a `200` whose values were read from the running process or OS. **If a key is present, it was
measured** — there is no fourth shape and no placeholder literal anywhere in this group.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/computer/control` | **`501`** `computer_control` — nothing is controlled |
| GET | `/api/computer/apps` | `200` `{running: null}` + `data_source: "unavailable"` — no app is enumerated |
| GET | `/api/computer/screenshot` | **`501`** `computer_screenshot` — no image payload, no capture (§4.3) |
| GET | `/api/computer/volume` | `200` `{volume: null, muted: null}` + `data_source: "unavailable"` |
| GET | `/api/computer/lock` | **`501`** `computer_lock` — the PC is **not** locked, so the client must not show a locked state |
| POST | `/api/computer/open` | **`501`** `computer_open` — no `Json` extractor, so a POST with or without a body is always `501` (never `422`). The request counter still increments. `{target}` is ignored |
| POST | `/api/computer/execute` | **`501`** `computer_execute` — **nothing is executed**; the UI gates this |
| GET | `/api/computer/processes` | `200` `{processes: null}` + `data_source: "unavailable"` |
| GET | `/api/computer/status` | `200` `{status, os, arch, server}` (+ `hostname` when `COMPUTERNAME` is non-empty). **No `cpu` key, no `memory` key** |
| GET | `/api/computer/memory` | `200` `{total: null, used: null, available: null, usage_percent: null}` + `data_source: "unavailable"` |
| GET | `/api/computer/scan` | `200` + `data_source: "unavailable"`, **no `network` key** — no scan is performed |
| GET | `/api/computer/time` | `200` `{timestamp}` from `SystemTime` — measured |
| GET | `/api/computer/ping` | `200` `{pong: true}` + `data_source: "unavailable"`, **no timing field** — the route has no real destination to reach |
| GET | `/api/computer/whois` | `200` `{status, os, arch, framework, server}` (+ `hostname` when `COMPUTERNAME` is non-empty) — **no longer degraded**; it now reports the same OS facts as `/api/system/whois`, minus that route's extra `data_source` marker |
| GET | `/api/computer/explorer` | **`501`** `computer_explorer` — nothing is opened |

All `501` bodies share the shape `{error: "not_implemented", status: 501, feature, detail, server}`;
every `unavailable` body carries `status: "ok"`, `data_source: "unavailable"`, a `detail`, and
`server: "ARIA-Axum-8002"`. `hostname` is **omitted**, never invented, when `COMPUTERNAME` is unset
or blank — render the device tile without a name in that case rather than substituting one.

`/api/system/*` mirrors `/api/computer/*` (`system.rs` vs `computer.rs`) with near-identical
bodies. The mobile client uses `/api/computer/*` as canonical and falls back to
`/api/system/*` on 404, since one of the two module sets may be retired during migration.
The `whois` pair now report the same OS facts, so either is acceptable for the header device tile.

### 4.3 Phase Airi backend additions (required, not yet implemented)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/system/cpu` | `{usage_percent, per_core[], temp_c, load_avg}` — unblocks the CPU tile |
| GET | `/api/system/disk` | `{total, used, available, usage_percent}` |
| GET | `/api/pc/state` | `GET` variant of the existing `POST` returning real idle time |
| GET | `/api/agents` | **exists but static** (`agents.rs:76-82`) — returns a hardcoded 4-name array with no per-agent status. Needs live `status` per agent |
| GET | `/api/tasks/pending` | queue depth + next task, for polling fallback |
| POST | `/api/daemon/task` | already exists — mobile uses it as an agent would (§4.4) |

### 4.3.1 Routes that exist but are not yet in this spec

Listed so the next revision does not rediscover them. None are on the mobile critical path.

| Method | Path | Source | Note |
| --- | --- | --- | --- |
| GET | `/api/system/health` | `core.rs:28` | alias of `/health` |
| GET | `/api/system/explorer`, `/api/system/code_exec` | `system.rs:29-30` | status stubs, desktop-only |
| GET | `/api/computer/explorer` | `computer.rs:31` | **`501`** `computer_explorer` |
| GET | `/api/skills/scan`, `/api/skills/search` | `skills.rs:26-27` | search/scan skills |
| POST | `/api/agents/research/batch` | `agents.rs:39` | batched research |
| GET | `/api/agents/geospatial/status` | `agents.rs:41` | God's-Eye view state |
| POST | `/api/agents/voice/process` | `agents.rs:42` | server-side voice |
| GET/POST | `/api/orb/state`, `/api/orb/phase`, `/api/orb/start`, `/api/orb/stop` | `daemon.rs:101-104` | drive the native wgpu orb. `POST /api/orb/phase` takes `{phase: idle\|thinking\|responding\|listening\|wisdom}` and returns `{status:"error", error:"Unknown phase: x"}` on a bad value |

The remaining modules merged into the router (`memory.rs`, `voice.rs`, `vision.rs`,
`files.rs`, `web.rs`, `proactive.rs`, `evolution.rs`, `learning.rs`, `github.rs`,
`social.rs`, `admin.rs`, `self_improvement.rs`, `lib.rs:25-46`) add further `/api/*` routes
that Phase Airi does not consume.

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
(`daemon.rs:257-284`), which is what `/api/agents/status` reads
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
(`daemon.rs:162-185`). **Claiming is not optional** — polling `GET /api/daemon/task`
(`daemon.rs:128-143`) never assigns, so a mobile client using GET would loop forever on the
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

The server key is `ARIA_API_KEY` (`state.rs:27`). If the variable is unset or blank the
server **generates a random key at startup and prints it to stdout** — a token issued in a
previous session stops working, and the mobile client sees an unexplained `401`. Settings
must therefore surface the "backend is using an ephemeral key" state, which is reported as
`security.key_source: "generated"` in `/api/system/status` and `ephemeral_key: true` in
`/api/auth/validate`.

| Method | Path | Token required | Notes |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | no (public) | returns the **placeholder** `"axum-jwt-token-placeholder"` — not a usable token (§0.2.4) |
| POST | `/api/auth/register` | no (public) | `{status, username, registered, server}`; no account is actually created |
| POST | `/api/auth/refresh` | no (public) | returns the placeholder `"axum-jwt-refreshed-token"` — the client cannot recover a `401` this way |
| POST | `/api/auth/logout` | **yes** | `{status, logged_out}`; no server-side session to revoke |
| GET | `/api/auth/validate` | **yes** | `{status, valid, method:"header", user{subject, role, scopes, ephemeral_key}, server}` |
| POST | `/api/auth/validate` | **yes** | also accepts `{token}` in the body and reports whether *that* token matches — the endpoint the mobile client uses to test a key pasted from Settings |
| GET | `/api/auth/profile` | **yes** | `{status, user, role, server}` |
| GET | `/api/auth/permissions` | **yes** | `{status, permissions: ["read","write","execute","admin"], server}` |
| GET | `/api/auth/roles` | **yes** | `{status, roles: ["admin","user","viewer"], server}` |
| GET | `/api/auth/sessions` | **yes** | `{status, sessions: []}` |
| GET | `/api/auth/webhooks` | **yes** | `{status, webhooks: []}` |

The client stores the key in the `airi_settings` Hive box and sends `Authorization: Bearer
<key>` (fallback `X-API-Key: <key>`) on every request. **Do not implement a login screen
against `/api/auth/login`** — it cannot produce a working token. The Settings screen should
instead offer a "paste ARIA API key" field, validate it with `POST /api/auth/validate`,
and show a warning whenever `security.key_source == "generated"` because the key will
change on the next backend restart.

### 4.7 Rate limits

**The server does enforce limits**, and has since `auth::guard` landed. The client must
still keep a local budget, but now because the server's is coarse enough to be disruptive
to a polling dashboard, not because the server is unlimited.

**Server-side (as implemented):**

| Property | Value |
| --- | --- |
| Algorithm | fixed window, keyed by client IP (`x-forwarded-for` → `x-real-ip` → socket peer) |
| Budget | **100 requests / 60 s, one flat limit for every path** — not per class |
| Public paths | counted too, so a `/health` probe loop can exhaust the window |
| On breach | `429` `{"error":"rate_limited","status":429}` + `Retry-After: <seconds>` |
| Every response | `X-RateLimit-Limit: 100`, `X-RateLimit-Remaining: <n>` |
| 401 responses | counted in `auth_failures`, surfaced in `/api/system/status` |

A per-class scheme (the 60/30/10 split below) is a *target*, not current behaviour. The
flat 100/min budget is the real constraint the client is written against: a 5 s dashboard
poll plus 3 s memory poll plus 5 s agents poll is ~48 req/min, which fits — but adding
`/api/computer/status` at 1 s does not, and the client will start seeing `429`s it did not
expect.

**Client-side budget (unchanged intent):**

| Class | Budget | Behaviour on breach |
| --- | --- | --- |
| `poll` (status, memory, agents) | 1 per 5 s, burst 3 | coalesce — drop the tick |
| `command` (control, lock, volume, open, screenshot) | 1 per 2 s, burst 5 | do **not** queue — every one of these is `501` or `unavailable` (§4.2), so a replay can never succeed |
| `execute` (`/api/computer/execute`) | 1 per 30 s | hard block with a countdown |
| `chat` | 1 per 10 s | queue |
| `daemon` (heartbeat/task/result) | 1 per 30 s | drop, never queue |
| `login` | 5 per 15 min | hard block |

The client honours `Retry-After` verbatim and should also read `X-RateLimit-Remaining` to
throttle *before* the `429` arrives. A `401` is **not** refreshable here (§0.2.4) — the
client must stop the replay loop and prompt the user for the key.

### 4.8 Error contract

Target shape — the middleware and most handlers currently return a **flat** error body, not
the nested object below. The client decodes **both**:

```json
// as implemented by the middleware (auth.rs:135-157)
{ "error": "unauthorized", "status": 401 }

// as implemented by body-level handler failures, e.g. daemon.rs:250-254
{ "status": "error", "error": "Missing agent_id or result" }

// TARGET shape
{ "error": { "code": "unknown_action", "message": "…", "retryable": false },
  "status": "error" }
```

Note that `status` is polymorphic in the current backend: the middleware puts an **integer
HTTP status** in it, handlers put the **string** `"error"`. `SystemStatus.status` therefore
cannot be a single typed field across both sources — decode it loosely.

| Code | HTTP | Retryable |
| --- | --- | --- |
| `unauthorized` (missing or invalid token) | 401 | **no** — cannot refresh (§0.2.4); re-prompt for the key |
| `forbidden` | 403 | no |
| `rate_limited` | 429 | yes, after `Retry-After` |
| `backend_offline` | — (transport) | yes, backoff |
| `unknown_action` (in-body, HTTP 200) | 200 | no — protocol mismatch |
| `internal` | 5xx | yes, exponential |

The server never emits a `token_expired` code — an expired and a malformed token are both
`unauthorized`. The client must not branch on a `token_expired` string.

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
(`assigned_to` in `daemon.rs:162-185`): if the WS pushes `task_available` for a task the
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
| Key distribution | The key is **not** discoverable by the client. It comes from `ARIA_API_KEY` on the PC, or from the random key the backend prints at startup. Shipping it inside the APK would make every install identical. |
| PIN / biometric | out of scope |
| Dangerous commands | `execute` and `lock` require an in-app confirmation dialog. `execute` is additionally rate-limited to 1/30 s. |
| Command allowlist | the Command screen only offers the kinds in §5.4; no arbitrary-path requests from the UI. |
| Logs | command bodies may contain user text; the log box is capped at 500 entries and truncates bodies to 200 chars. |
| CORS | `cors_layer()` in `lib.rs:52-64` allows **any** origin, any method, any header. Acceptable for a loopback-bound POC and must be replaced with an explicit origin list before LAN exposure. It is not, as previously stated, a bare `CorsLayer::permissive()`. |
| WS auth | `/ws` is public and unauthenticated (§0.2.5). Nothing on the current socket is sensitive — it is an echo loop — but the exemption must be removed before typed frames carry task data. |

---

## 8. Implementation status

| Item | Status |
| --- | --- |
| `v6/MOBILE_SYNC_SPEC.md` | this document — verified against `src/` on 2026-09-29 |
| `v6/airi_mobile/pubspec.yaml` | created; dependencies verified, **platform folders missing** (see §8.1) |
| `v6/airi_mobile/lib/main.dart` | created |
| `v6/airi_mobile/lib/models/{pc_state,task,message}.dart` | created |
| `v6/airi_mobile/lib/services/{backend_service,offline_queue,settings_service,notification_service}.dart` | created |
| `v6/airi_mobile/lib/screens/{dashboard,command,settings}.dart` | created |
| Flutter SDK | **not installed** — source only |
| `HeartbeatResponse` compile fix (`daemon.rs:78-82`) | **RESOLVED** — `cargo build --release` succeeds |
| Real auth middleware | **RESOLVED** — `auth::guard`, bearer + `X-API-Key`, constant-time |
| Rate limiting (server) | **RESOLVED** — 100 req/min per IP, 429 + `Retry-After` |
| `GET /api/system/cpu` | outstanding |
| `GET /api/system/disk` | outstanding |
| Real `POST /api/pc/state` | outstanding (still hardcoded) |
| `/api/auth/login` returning the real key | outstanding (still a placeholder) |
| Auth on `/ws` | outstanding |
| WS broadcast of `task_available` / `task_result` | outstanding |
| WS `heartbeat` frame (§3.3) | outstanding |
| Anything enqueuing into `task_queue` | outstanding — the queue is always empty, so the whole task flow is inert |
| FCM sender | outstanding |
| Screenshot image payload | outstanding |

### 8.1 Build blockers for the Flutter client

1. **No `android/` or `ios/` directory exists.** `v6/airi_mobile` contains only
   `pubspec.yaml`, `analysis_options.yaml` and `lib/`. Run
   `flutter create --platforms=android,ios .` before the project will build, otherwise
   `flutter run` has no target and FCM cannot initialise.
2. **No FCM configuration.** `firebase_core` + `firebase_messaging` are declared but
   `google-services.json` / `GoogleService-Info.plist` are absent. Android additionally
   needs `com.google.gms.google-services` in `android/build.gradle`.
3. **`flutter_local_notifications` ≥ 15 requires core library desugaring** on Android:
   `android/app/build.gradle` needs
   `compileOptions { coreLibraryDesugaringEnabled true }` plus
   `coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.1.4'` and the matching
   `dependencies` entry. Without it the Android build fails at compile time.
4. **`intl` is pinned to `^0.19.0`** because `flutter_local_notifications` does not yet
   support `intl` 0.20. Do not bump it.
5. **`hive` 2.2.3 needs no code generation** here — all three boxes
   (`airi_settings`, `airi_offline_queue`, `airi_cache`, `airi_log`) store
   primitives/`Map`s, so `hive_generator` is correctly absent from `dev_dependencies`.
   If a `QueuedCommand` type adapter is introduced later, add `hive_generator` +
   `build_runner`.
6. **Android cleartext HTTP** to `http://<lan-ip>:8002` is blocked by default from API 28.
   The app needs a `network_security_config.xml` permitting cleartext for the specific
   backend host, otherwise every connection fails with a confusing socket error. See the
   transport rule in §7 — cleartext to a non-loopback host should be an explicit,
   user-visible opt-in, not a blanket manifest flag.

### Dependency note

`pubspec.yaml` uses **`web_socket_channel`**, not `websocket_client`. The latter is
deprecated and unmaintained (last release 2018) and does not support the RFC 6455
control-frame ping the reconnect logic in §1.4 depends on. `web_socket_channel` is its
maintained successor with the same `WebSocketChannel` API surface.
