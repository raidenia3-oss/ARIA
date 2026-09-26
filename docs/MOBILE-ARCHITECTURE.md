# AURA Mobile (AME) — Architecture & Integration Guide

Complete mobile integration combining Linux, launcher, and remote sync.

## Architecture Overview

### Mobile Device Stack

```
┌──────────────────────────────────────────────────────┐
│  Android Device (Pixel, Samsung, OnePlus, etc.)      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  AURA Launcher (Flutter)                             │
│  ├─ Home screen replacement                          │
│  ├─ mDNS discovery (aura.local:8000)                │
│  ├─ WebSocket telemetry (ws://aura.local/ws/mobile) │
│  ├─ REST chat client (/api/chat)                    │
│  ├─ Mode toggle: Local ↔ Remote                     │
│  ├─ Push notifications                              │
│  └─ Energy saving mode                              │
│                                                      │
├─ LOCAL MODE ──────────────────────────────────────┤
│  Termux / Proot-distro (Ubuntu 22.04)               │
│  ├─ Linux userspace (bash, apt, wget, curl)         │
│  ├─ Python 3.11 + backend/main.py                   │
│  ├─ Go tools (arm64-compiled):                      │
│  │  ├─ aura-scanner (65k ports)                     │
│  │  ├─ aura-resolver (DNS bulk)                     │
│  │  ├─ aura-enum (subdomain)                        │
│  │  ├─ aura-c2-server (beaconing)                   │
│  │  ├─ aura-c2-agent (agent)                        │
│  │  └─ aura-c2-client (CLI)                         │
│  ├─ Ruby tools + gems                               │
│  ├─ SQLite database (local)                         │
│  └─ Accessible via: localhost:8000                  │
│                                                      │
├─ REMOTE MODE ─────────────────────────────────────┤
│  Desktop AURA OS (Detected via mDNS)                │
│  ├─ mDNS broadcast: aura.local                      │
│  ├─ Desktop location: 192.168.1.X:8000              │
│  ├─ WebRTC streaming (Flet client protocol)         │
│  ├─ Desktop keyboard/mouse via Godot               │
│  ├─ Full system access                              │
│  └─ Chat + skills sync                              │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Key Decisions

### Why Hybrid Termux + Launcher?

| Requirement | Solution | Status |
|---|---|---|
| No root required | Termux (Android 11+) | ✅ |
| Linux environment | proot-distro Ubuntu 22.04 | ✅ |
| Offline capability | Python backend + SQLite on-device | ✅ |
| Remote access | mDNS + WebSocket + WebRTC | ✅ (existing) |
| Cross-platform | Flutter (iOS/Android/Web) | ✅ |
| Go tools on mobile | Cross-compile to arm64 | ✅ (planned) |

### Why Not Full Linux Desktop on Mobile?

- **Waydroid**: Requires kernel patches, not supported on most phones
- **UserLAnd**: Good but no home screen replacement integration
- **Kali Nethunter**: Requires rooted device (security concern)
- **Pure remote**: No offline capability, defeats purpose of "mobile"

### Why Termux + Proot-distro?

- **Termux**: Provides package manager, terminal, and development environment
- **Proot-distro**: Installs full Ubuntu/Debian rootfs without root
- **Combined**: Gives full Linux environment with AURA tools
- **Launcher integration**: Flutter launcher manages both modes
- **Battery**: Can pause Linux services when screen off

## Implementation Plan (6 Tasks)

### TAREA 1: docs/MOBILE-ARCHITECTURE.md ✅

This file — architecture documentation.

### TAREA 2: Extend Flutter Launcher

**File**: `aura-os/mobile-launcher/lib/main.dart`

Add Termux integration:

```dart
// New dependencies in pubspec.yaml:
//   termux: ^0.1.0
//   flutter_webrtc: ^0.9.0
//   mdns_plugin: ^2.0.0

class TermuxService {
  // Launch terminal in Termux
  static Future<void> openTerminal() async {
    // Use Termux plugin or intent
  }

  // Run AURA command in Termux
  static Future<String> runAuraCommand(String cmd) async {
    // e.g. aura-scanner -h 192.168.1.1 -p 1 -e 1000
  }

  // Check if Proot-distro is installed
  static Future<bool> isLinuxInstalled() async {
    // Check for Ubuntu rootfs
  }
}
```

Add mode toggle UI:

```dart
enum LauncherMode { localLinux, remoteDesktop }

class ModeToggle extends StatelessWidget {
  // Toggle between running Linux locally
  // vs. streaming desktop AURA OS
}
```

### TAREA 3: Termux Bootstrap Script

**File**: `scripts/termux-bootstrap.sh`

```bash
#!/bin/bash
# Installs full AURA Linux environment in Termux
set -e

# Update Termux
pkg update -y
pkg upgrade -y

# Install core packages
pkg install -y \
  proot-distro \
  python git wget curl unzip \
  golang nodejs ruby \
  net-tools dnsutils openssh

# Install Ubuntu 22.04 via proot-distro
proot-distro install ubuntu-22.04

# Install Python backend
pip install fastapi uvicorn httpx

# Install Go tools (arm64)
# Pre-compiled binaries provided by cross-compile script
cp /path/to/go-tools/* $PREFIX/bin/

# Install Ruby tools
gem install bundler

# Start backend
python backend/main.py &
```

### TAREA 4: Cross-Compile Go Tools

**File**: `scripts/cross-compile-go-tools.sh`

```bash
#!/bin/bash
# Cross-compile all 6 Go tools for Android arm64

cd aura-os/go-tools
export GOOS=linux
export GOARCH=arm64
export CGO_ENABLED=0

for tool in scanner resolver enum c2-agent c2-server c2-client; do
  go build -o dist/android/${tool} -ldflags "-s -w" ./cmd/${tool}/
done
```

### TAREA 5: WebSocket Mobile Endpoint

**File**: `backend/main.py` (existing → add)

```python
# New WebSocket endpoint for mobile telemetry
@router.websocket("/api/ws/mobile")
async def mobile_websocket(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = {
            "timestamp": time.time(),
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
            "mode": request.mode,  # local or remote
        }
        await websocket.send_json(data)
        await asyncio.sleep(1)
```

### TAREA 6: Validation

Validation commands:
```bash
# Python syntax
python -m py_compile backend/main.py
python -m py_compile scripts/termux-bootstrap.sh

# Flutter analyze
flutter analyze aura-os/mobile-launcher/

# Test mDNS discovery from mobile
nslookup aura.local

# Test WebRTC connection
curl -s http://aura.local:8000/webrtc/offer
```

## Connection Flow

### Discovery (mDNS)
1. AURA Launcher broadcasts via mDNS (or uses network_utils.py UDP discovery)
2. Desktop AURA OS responds if running
3. Launcher auto-detects: `ws://aura.local:8000/ws/mobile`

### Mode Selection
```
User toggles Local ↔ Remote in launcher UI:

LOCAL MODE:
  ├─ Termux backend runs: 127.0.0.1:8000
  ├─ All tools available (scanner, resolver, enum, C2)
  ├─ Python backend + SQLite local
  └─ No internet required

REMOTE MODE:
  ├─ WebRTC stream from desktop
  ├─ mKbd input via Godot
  ├─ Full system access
  └─ Chat + skills sync
```

## Termux Setup Guide

### Prerequisites
- Android 11+ (for Termux: API 21+)
- 2GB+ free storage
- Internet connection for initial setup

### Installation
```bash
# 1. Install Termux from F-Droid (play store version may be outdated)
#    https://f-droid.org/en/packages/com.termux/

# 2. Run bootstrap script
curl -s https://raw.githubusercontent.com/TU_USUARIO/AURA/main/scripts/termux-bootstrap.sh | bash

# 3. Configure proot-distro
proot-distro login ubuntu-22.04

# 4. Inside Ubuntu:
cd /opt/aura
python backend/main.py --port 8000
```

## File Manifest

| File | Role |
|---|---|
| `aura-os/mobile-launcher/` | Flutter launcher (home screen replacement) |
| `scripts/termux-bootstrap.sh` | Termux environment setup |
| `scripts/cross-compile-go-tools.sh` | Cross-compile Go tools for Android |
| `backend/main.py` (extend) | Add `/api/ws/mobile` WebSocket endpoint |
| `mobile_client/app.py` | WebRTC streaming (reuse for remote mode) |
| `mobile_client/network_utils.py` | UDP discovery (reuse in Flutter) |
| `aura-os/go-tools/` | 6 CLI tools to cross-compile |

## Security Notes

- **Termux sandbox**: Limited filesystem access (uses `/data/data/com.termux/files/`)
- **Proot**: No root, but `/sdcard` accessible via storage permission
- **mDNS**: Local network only, no internet exposure
- **WebRTC**: End-to-end encrypted, no server relay needed for local stream
- **Push notifications**: Use Firebase for remote mode activation

## Known Limitations

1. **Android 11+**: Scoped storage limits some operations
2. **Battery**: Linux services will drain battery (use energy saving mode)
3. **Storage**: Ubuntu rootfs takes ~1GB, tools add ~500MB
4. **GPU**: No GPU passthrough for Go tools (CPU-only for scanning/resolving)
5. **iOS**: No equivalent to Termux — iOS users get Remote Mode only

## References

- **mDNS**: Existing in `mobile_client/network_utils.py` (UDP broadcast)
- **WebRTC**: Existing in `mobile_client/app.py` (Flet client protocol)
- **Backend**: Existing `backend/main.py` (117 routes, FastAPI)
- **Go tools**: Existing `aura-os/go-tools/` (6 binaries, stdlib only)
- **Termux**: https://termux.com/ | Proot-distro: https://github.com/termux/proot-distro
- **Flutter mobile-launcher**: Existing `aura-os/mobile-launcher/`

---

**Status**: Architecture defined. Next: Implementation (TAREAS 2-5).  
**Last Updated**: September 3, 2026
