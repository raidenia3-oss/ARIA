# Airi — ARIA v6.0 Mobile Client

Flutter companion app for ARIA OS v6.0. Connects to the Rust/Axum backend on
`127.0.0.1:8002`, shows live PC state, and issues commands to the desktop agent.

The wire protocol is specified in [`../MOBILE_SYNC_SPEC.md`](../MOBILE_SYNC_SPEC.md).
That document is the source of truth — this README only covers how to build, run and
connect.

---

## Prerequisites

| Requirement | Version | Notes |
| --- | --- | --- |
| Flutter SDK | **3.10 or newer** (3.x) | `pubspec.yaml` pins `sdk: ">=3.0.0 <4.0.0"` |
| Dart SDK | bundled with Flutter | — |
| ARIA backend | v6.0 Axum, running | see [Running the backend](#running-the-backend) |
| Android SDK | API 24+ | only for Android builds |
| Xcode | 14+ | only for iOS builds |
| Auth key | `ARIA_API_KEY` | see [Authentication](#authentication) — **required**, there is no working login |

Check your install:

```bash
flutter --version
flutter doctor
```

`flutter doctor` must be clean for the Android *and* iOS toolchains you intend to use.

---

## Setup

### 1. Generate the platform folders

The repository ships `pubspec.yaml`, `analysis_options.yaml` and `lib/` only — there is
**no `android/` or `ios/` directory yet**, so the project will not build as-is:

```bash
cd v6/airi_mobile
flutter create --platforms=android,ios --org com.aria .
```

This creates `android/` and `ios/` and leaves the existing `lib/` untouched.

### 2. Fetch dependencies

```bash
flutter pub get
```

All direct dependencies are pinned to ranges that resolve on Dart 3:

| Package | Version | Why |
| --- | --- | --- |
| `dio` | `^5.4.3+1` | HTTP + JSON for the REST surface |
| `web_socket_channel` | `^2.4.5` | RFC 6455 socket for `/ws` |
| `hive` / `hive_flutter` | `^2.2.3` / `^1.1.0` | settings, offline queue, caches |
| `path_provider` | `^2.1.3` | Hive directory resolution |
| `flutter_local_notifications` | `^17.1.0` | local notification rendering |
| `firebase_core` / `firebase_messaging` | `^2.27.0` / `^15.0.4` | FCM push (not yet wired server-side) |
| `uuid` | `^4.2.2` | device id + idempotency keys |
| `intl` | `^0.19.0` | **do not bump** — `flutter_local_notifications` does not support 0.20 yet |

> `websocket_client` is deliberately **not** used. It is unmaintained (last release 2018)
> and has no control-frame ping support, which the reconnect logic in §1.4 of the spec
> depends on.

### 3. Configure FCM (optional, push only)

`firebase_core` and `firebase_messaging` are declared, so the app will not start until FCM
has credentials. To skip push entirely for local development, remove both from
`pubspec.yaml` and the `NotificationService` bootstrap from `main.dart`.

Otherwise:

- **Android** — drop `android/app/google-services.json`, add to `android/build.gradle`:
  ```groovy
  plugins { id("com.google.gms.google-services") version "4.4.2" apply false }
  ```
  and to `android/app/build.gradle`:
  ```groovy
  plugins { id("com.google.gms.google-services") }
  ```
- **iOS** — add `GoogleService-Info.plist` to the Runner target and the `Firebase` pod.

### 4. Android: desugaring and cleartext

`flutter_local_notifications` ≥ 15 requires **core library desugaring**. Without it the
Android build fails at compile time. In `android/app/build.gradle`:

```groovy
android {
  compileOptions {
    coreLibraryDesugaringEnabled true
    sourceCompatibility JavaVersion.VERSION_1_8
    targetCompatibility JavaVersion.VERSION_1_8
  }
}
dependencies {
  coreLibraryDesugaring "com.android.tools:desugar_jdk_libs:2.1.4"
}
```

The backend serves **cleartext HTTP**. Android blocks it by default from API 28, so add
`android/app/src/main/res/xml/network_security_config.xml` and reference it from the
manifest:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <!-- Flip to true once you accept the tradeoff in spec §7. -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">10.0.2.2</domain>
    </domain-config>
</network-security-config>
```

Keep `cleartextTrafficPermitted="false"` as the base — cleartext should be a deliberate,
host-scoped opt-in, not a blanket manifest flag.

### 5. Run

```bash
flutter devices
flutter run -d <device-id>
```

---

## Running the backend

The mobile client talks to the Axum binary, not the old FastAPI server.

```powershell
cd C:\Users\User\Downloads\AURA\v6\axum-poc
cargo build --release
.\target\release\aria-axum-poc.exe
```

It binds `127.0.0.1:8002` only. Confirm it is up:

```bash
curl http://127.0.0.1:8002/health
```

The binary also auto-launches the native wgpu orb window and the autonomy daemon on
startup, so a GPU window will appear alongside the console.

---

## Authentication

**There is no working login flow.** `POST /api/auth/login` returns a hardcoded placeholder
string, not a real token, and `POST /api/auth/refresh` cannot recover from a `401`. The
app therefore authenticates with the backend's shared API key, which you supply manually.

Every route except `/health`, `/ws` and the three `/api/auth/*` bootstrap paths requires:

```
Authorization: Bearer <ARIA_API_KEY>
```

Get the key one of two ways:

1. **Recommended — pin it.** Set the environment variable before starting the backend:
   ```powershell
   $env:ARIA_API_KEY = "your-long-random-string"
   .\target\release\aria-axum-poc.exe
   ```
2. **Leave it unset.** The backend generates a random key and **prints it to stdout** at
   startup. Copy it from the console.

Then, in the app's **Settings** screen:

1. Set the **Backend URL** (§ [Connecting](#connecting)).
2. Paste the key into the **API key** field.
3. Tap **Validate**. The app calls `POST /api/auth/validate` with the token in the body and
   reports `valid: true/false`.

> If you generated the key (option 2), it changes on **every backend restart** and any
> previously stored key will `401`. The app surfaces this: `GET /api/system/status` reports
> `security.key_source`, and Settings shows a warning when it reads `"generated"`.

---

## Connecting

### Backend URL

Default: `http://127.0.0.1:8002`, editable in Settings at runtime.

| Where the app runs | Backend URL to enter | Notes |
| --- | --- | --- |
| Android emulator | `http://10.0.2.2:8002` | Loopback is rewritten automatically — `127.0.0.1` and `localhost` are mapped to the emulator's host alias |
| iOS simulator | `http://127.0.0.1:8002` | Shares the host network stack |
| Physical device (same Wi-Fi) | `http://<pc-lan-ip>:8002` | See the warning below |

Enter the host bare (`192.168.1.50:8002`) or with a scheme — `normalizeBaseUrl` adds
`http://` if you omit it. `https://` is accepted and upgrades the socket to `wss://`.

### ⚠️ Reaching the backend from a phone over the LAN

The Axum server hardcodes its bind address to `127.0.0.1:8002` in
`v6/axum-poc/src/main.rs:48`, so **a phone on the same Wi-Fi cannot reach it**. Loopback
only means emulator and simulator only.

To test on a real device you must change the bind to `0.0.0.0:8002`. Before doing that,
read spec §7 and §0.2.5 — `cors_layer()` allows any origin and `/ws` is unauthenticated.
Bind to `0.0.0.0` only on a network you trust, and set `ARIA_API_KEY`.

### WebSocket

`ws://<host>:8002/ws`. On open the server immediately sends a `connected` frame, then acts
as an echo loop. The app:

1. Opens the socket and waits for `connected` — that is the "backend is live" signal.
2. Sends an `identify` frame with its `device_id` (UUID v4, persisted in Hive).
3. Runs a 30 s control-frame ping loop to detect a dead TCP connection.
4. Reconnects with exponential backoff: 1 s, 2 s, 4 s, 8 s, then 30 s, ±20% jitter.
5. Replays the offline command queue after every successful reconnect.

The current server has no `capabilities` frame, so all commands go over REST.

### Endpoints the app actually calls

| Call | Purpose |
| --- | --- |
| `GET /health` | reachability, uptime, version |
| `GET /api/system/status` | dashboard poll — the primary state source |
| `GET /api/system/whois` | header device info |
| `GET /api/system/time` | clock-skew check |
| `GET /api/system/memory` | memory gauge |
| `GET /api/computer/*` | the Command screen (apps, volume, lock, open, screenshot, execute, processes, status) |
| `POST /api/chat` | chat, 60 s server timeout — the client uses 70 s |
| `GET /api/agents/status` | swarm + daemon agents |
| `GET /api/skills`, `POST /api/skills/run` | skill list and invocation |
| `POST /api/auth/validate` | key validation from Settings |
| `POST /api/daemon/heartbeat` | registers the phone as a daemon agent |
| `POST /api/daemon/task`, `POST /api/daemon/result` | agent work loop |

**CPU shows `—`.** No CPU telemetry endpoint exists yet (`/api/system/cpu` is in the spec
as an outstanding backend addition). Screenshot returns a status stub with no image.

### Rate limits

The backend enforces **100 requests / 60 s per IP**, flat, across every path including
public ones. Every response carries `X-RateLimit-Remaining`; a breach returns `429` with
`Retry-After`. The client additionally throttles locally so a polling dashboard stays
inside that budget. See spec §4.7.

---

## Features

**Dashboard**
- Live backend status: uptime, requests served, chats processed, daemon agents, pending
  tasks, completed results
- Memory gauge
- Backend identity card (hostname, OS, arch) with clock-skew indicator
- Connection state indicator: disconnected / connecting / connected / degraded
- CPU tile, shown as `—` until `/api/system/cpu` ships

**Command**
- `open`, `volume`, `lock`, `screenshot`, `apps`, `processes`, `execute`
- `lock` and `execute` require an explicit confirmation dialog
- `execute` is locally rate-limited to once per 30 s with a countdown
- Offline queue: every command is enqueued locally first and sent when the backend
  returns, with an idempotency key per entry
- Manual "Retry now" to flush the queue

**Chat**
- `/api/chat` with a 70 s client timeout (the backend's own limit is 60 s)
- Queued when offline, never dropped

**Settings**
- Backend URL with emulator loopback rewriting
- API key entry and validation
- Warning when the backend is using an ephemeral (regenerated-per-boot) key
- Warning when plaintext HTTP is pointed at a non-loopback host
- Per-category push toggles: `taskAvailable`, `taskResult`, `systemAlert`,
  `pcStateChange` (last one defaults off)

**Resilience**
- WebSocket reconnect with jittered exponential backoff, reset after 60 s stable
- Serial offline-queue replay — never parallel, ordered by creation time
- Commands expire after 24 h; `attempts >= 5` marks an entry failed rather than
  retrying forever
- `inflight` entries are reset to `pending` on app start, so a crash mid-send cannot
  strand a command
- Hive-backed cache renders last-known-good state immediately, then upgrades to live —
  never a spinner over data already held

**Daemon mode**
- The phone registers itself as an `airi_mobile-<device_id>` agent via
  `POST /api/daemon/heartbeat` every 30 s
- Claims work with `get_pending` (**POST only** — the `GET` variant never assigns, so a
  client that polls GET loops on the same task forever)
- Reports status and results back
- The phone appears on the desktop dashboard under role `USB-ARIA Daemon`

---

## Known gaps

Backend-side, not fixable in this repo without touching `v6/axum-poc`:

- No CPU or disk telemetry endpoints — the CPU tile stays `—`
- `POST /api/pc/state` returns hardcoded values and discards the request body
- `task_available` / `task_result` are not broadcast over the socket; the client
  reconciles via a `completed_results` delta in `/api/system/status`
- No server `heartbeat` frame — the client polls `/api/system/status` instead
- The task queue is never written to, so no work is ever available to claim
- No screenshot image payload
- FCM is not wired on the backend, so push notifications never arrive

Client-side, still open:

- No `android/` or `ios/` directories in the repo — run `flutter create` (§ Setup 1)
- Token is stored in plain Hive; a release build needs `flutter_secure_storage`
- PIN / biometric lock is out of scope
