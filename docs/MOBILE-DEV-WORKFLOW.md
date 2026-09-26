# AURA OS Mobile (AME) — Development & Modification Workflow

Guía para desarrolladores y agentes de IA (Kilo, Claude, Copilot) sobre cómo modificar, mejorar y rebuildar el componente móvil de AURA OS.

## 📂 Project Structure (Mobile)

```
aura-os/mobile-launcher/
├── lib/
│   └── main.dart          # Flutter launcher UI (home screen replacement)
├── pubspec.yaml           # Dart dependencies + version
├── key.properties         # Keystore config (for release builds)
├── build_mobile.py        # Build automation
└── README.md

mobile_client/              # Flet client (WebRTC streaming)
├── app.py                 # Python/Flet UI (1412 líneas)
├── network_utils.py       # UDP mDNS discovery
├── build_mobile.py        # Flet build automation
└── requirements.txt

backend/mobile/             # Backend mobile sync
├── sync.py                # WebSocket sync manager (extendido)
└── ame_client.py          # AME client connection

scripts/                    # Build & deploy scripts
├── build-mobile-apk.sh    # Release APK build (signing + verification)
├── dev-mobile.sh          # Development build (hot reload)
├── termux-bootstrap.sh    # Install Linux env on Android device
└── cross-compile-go-tools.sh  # Compile Go tools to arm64

backend/main.py             # Mobile REST endpoints
    ├── /api/mobile/devices  # List discovered AURA devices
    ├── /api/mobile/mode     # Get/set launcher mode (local/remote)
    ├── /api/mobile/termux/cmd  # Execute whitelisted command
    └── /api/mobile/sync/{id}  # WebSocket sync
```

---

## 🛠️ Development Setup

### Prerequisites

| Requirement | Version | Install |
|---|---|---|
| **Flutter SDK** | 3.16+ | https://flutter.dev/docs/get-started/install |
| **Android SDK** | API 34 | `sdkmanager "build-tools;34.0.0"` |
| **JDK** | 11+ | https://openjdk.java.net |
| **Device/Emulator** | Android 11+ | Android Studio AVD |
| **Python** | 3.11+ | `.venv/` |

### Environment Setup

```bash
# 1. Install Flutter
git clone https://github.com/flutter/flutter.git -b stable
export PATH="$PATH:`pwd`/flutter/bin"

# 2. Install Android dependencies
flutter doctor  # Fix all issues

# 3. Python backend
cd backend
pip install -r requirements.txt

# 4. Verify
python -c "from backend.main import app; print('Backend OK')"
```

---

## 🔧 Modifying the Flutter Launcher

### Common Modifications

#### 1. Theme/UI Changes
```dart
// File: aura-os/mobile-launcher/lib/main.dart
// Edit class: AuraLauncherApp
// Theme: ColorScheme.fromSeed(seedColor: Color(0xFF0a0e27))

// Dark theme background:
backgroundColor: const Color(0xFF0a0e27),

// Surface (cards):
color: const Color(0xFF1a1f3a),
```

#### 2. Add New Mode Toggle Option
```dart
// In ModeToggle widget, add new enum value:
enum LauncherMode { localLinux, remoteDesktop, splitView }

// Add button in ModeToggle.build():
_buildModeButton(
  LauncherMode.splitView,
  'Split View',
  Icons.screen_split,
  Colors.purple,
),
```

#### 3. Add Terminal Command
```dart
// In _AuraHomePageState, add command to UI:
IconButton(
  onPressed: () => _termux.runCommand("aura-scanner -h 192.168.1.0/24"),
  icon: const Icon(Icons.search),
),
```

#### 4. Add WebSocket Message Handler
```dart
// Extend AuraSyncService.connect():
_channel.stream.listen((message) {
  final data = jsonDecode(message) as Map<String, dynamic>;
  
  if (data['type'] == 'new_notification') {
    // Handle notification from backend
    _showNotification(data['data']);
  }
  
  onTelemetry?.call(data);
});
```

### Validation After Changes

```bash
# Dart syntax check (no Flutter needed)
dart analyze aura-os/mobile-launcher/lib/

# Or via Flutter
cd aura-os/mobile-launcher
flutter analyze

# Run tests (if any)
flutter test
```

---

## 🔧 Modifying Backend Mobile Endpoints

### Backend mobile endpoints are in `backend/main.py` (lines ~2159-2230)

#### Add a New REST Endpoint
```python
# In backend/main.py, after mobile routes block:
@app.post("/api/mobile/mi-nueva-ruta", tags=["Mobile"])
async def mobile_custom_action(request: Request):
    body = await request.json()
    # Validate input
    if not body.get("required_field"):
        raise HTTPException(status_code=400, detail="required_field is required")
    # Process
    result = do_something(body)
    return {"status": "ok", "data": result}
```

#### Add a New WebSocket Action
```python
# In backend/mobile/sync.py, extend sync_data():
elif action == "mi_nueva_accion":
    param = payload.get("param", "")
    result["data"] = {"processed": process(param)}
```

#### Validation
```bash
# Python syntax
python -m py_compile backend/main.py
python -m py_compile backend/mobile/sync.py

# Import check
python -c "from backend.main import app; routes = [r.path for r in app.routes if r.path.startswith('/api/mobile')]; print(routes)"

# Test new sync actions
python -c "
import asyncio
from backend.mobile.sync import SyncManager
async def t():
    sm = SyncManager()
    print(await sm.sync_data(None, {'action': 'mi_nueva_accion', 'data': {}}))
asyncio.run(t())
"
```

⚠️ **No tocar**:
- `backend/auth/` — No modificar archivos de auth
- `backend/security_manager.py` — Dejar intacto (module aislado)
- `tools/security_assessment/` — Módulo de seguridad aislado
- `.env` / `.env.*` — Credenciales, no modificar

---

## 🔄 Development Workflow (Iterative)

### 1. Quick Change Test (No Rebuild)

```bash
# 1. Modify Dart code
# 2. Hot reload (device must be connected):
cd aura-os/mobile-launcher
flutter run

# 3. Or hot reload on connected device:
flutter attach
# Press 'r' in terminal for hot reload
```

### 2. Debug Build (Quick APK for testing)

```bash
# Build debug APK (no signing required)
cd aura-os/mobile-launcher
flutter build apk --debug --split-per-abi

# Install directly
adb install -r build/app/outputs/apk/debug/app-arm64-v8a-release.apk

# Or install all:
for f in build/app/outputs/apk/debug/*-release.apk; do
  adb install -r "$f"
done
```

### 3. Dev Build (Full development cycle)

```bash
# Run dev build helper script
bash scripts/dev-mobile.sh build    # Build debug APK
bash scripts/dev-mobile.sh test     # Build + install on device
bash scripts/dev-mobile.sh watch    # Hot reload mode
bash scripts/dev-mobile.sh lint     # Analyze code
bash scripts/dev-mobile.sh all      # Full dev cycle
```

### 4. Release Build (Full APK signing)

```bash
# Only for production releases
bash scripts/build-mobile-apk.sh 2.1.1

# Manual steps:
# 1. Run script
# 2. Enter keystore password
# 3. Sign + verify APK
# 4. Upload to Google Play
```

---

## 🔨 AI Agent Workflow (How Claude/Copilot Can Help)

### When Kilo/Claude/Copilot is asked to fix or improve AME:

### Step 1: Understand Context
```bash
# Read these files first
README.md          # Project overview
docs/ARCHITECTURE.md # System design
QUICK-START.md     # Quick setup
docs/MOBILE-ARCHITECTURE.md  # Mobile-specific architecture
docs/MOBILE-DEV-WORKFLOW.md  # This file
```

### Step 2: Identify What to Change
| Component | File | Language | Validation |
|---|---|---|---|
| Launcher UI | `aura-os/mobile-launcher/lib/main.dart` | Dart | `flutter analyze` |
| Sync actions | `backend/mobile/sync.py` | Python | `py_compile` |
| Mobile endpoints | `backend/main.py` | Python | `py_compile` |
| Termux bootstrap | `scripts/termux-bootstrap.sh` | Bash | `bash -n` |
| APK build | `scripts/build-mobile-apk.sh` | Bash | `bash -n` |

### Step 3: Make Changes
- Keep Python files < 250 lines (split if needed)
- Add docstrings to all public functions
- Follow existing code patterns
- Don't add external dependencies without checking

### Step 4: Validate Changes
```bash
# Validate Python
python -m py_compile <modified_file>.py

# Validate Bash
bash -n <modified_file>.sh

# Validate Dart (if Flutter installed)
cd aura-os/mobile-launcher && flutter analyze

# Run tests
python -m pytest tests/ -q --tb=no -x
```

### Step 5: Build & Test
```bash
# Quick test build
bash scripts/dev-mobile.sh build

# If on device:
bash scripts/dev-mobile.sh test

# Full release (only for production)
bash scripts/build-mobile-apk.sh <new_version>
```

### Step 6: Document Changes
- Update `CHANGELOG.md` with changes
- Update `docs/ARCHITECTURE.md` if architecture changed
- Update `docs/MOBILE-ARCHITECTURE.md` if mobile changed
- Update this file if workflow changed

---

## 🐛 Common Fixes & Bug Patterns

### Fix 1: Firebase/Dependencies Not Available
```bash
# In termux-bootstrap.sh:
# Add missing packages:
pkg install -y termux-services
pip install firebase-admin  # If needed
```

### Fix 2: mDNS Discovery Not Finding Desktop
```bash
# On desktop, verify:
avahi-broadcast -c "_aura._tcp"  # Should show service

# On mobile, verify:
# mDNS uses UDP port 5353
# Ensure WiFi multicast is enabled
```

### Fix 3: WebSocket Connection Drops
```bash
# In backend/mobile/sync.py:
# Check connection handling:
except WebSocketDisconnect:
    await self.remove_connection(websocket)  # Clean up
```

### Fix 4: Termux Storage Not Working
```bash
# In Termux app (not AURA):
termux-setup-storage  # Grant storage permissions
# Then symlink:
ln -s ~/storage/shared /sdcard  # If needed
```

### Fix 5: Go Tools Not Found on Android
```bash
# In termux-bootstrap.sh:
# Ensure Go tools are copied:
cp aura-tools/* $PREFIX/bin/
# Or use full path in commands:
~/../usr/share/aura-tools/aura-scanner
```

---

## 📱 Mobile Feature Checklist

Before adding a new feature, verify these work:

- [ ] Launcher opens on phone boot
- [ ] mDNS discovers desktop AURA OS (`aura.local:8000`)
- [ ] WebSocket connects (telemetry shows CPU/RAM)
- [ ] REST endpoints respond (`/api/chat`, `/api/health`)
- [ ] Local mode starts (Termux backend on `localhost:8000`)
- [ ] Remote mode connects (WebRTC stream starts)
- [ ] Mode toggle switches cleanly
- [ ] Energy saving activates on inactivity
- [ ] Notifications appear
- [ ] Back button works (doesn't exit app on root navigation)

---

## 🚀 Release Checklist

### Before Release

1. [ ] Version updated in `pubspec.yaml`
2. [ ] Version in `VERSION` file matches
3. [ ] CHANGELOG.md updated
4. [ ] All tests pass (`pytest tests/`)
5. [ ] `flutter analyze` clean
6. [ ] `bash -n scripts/*.sh` clean
7. [ ] `python -m py_compile backend/` clean

### Release Build

```bash
bash scripts/build-mobile-apk.sh <new_version>

# Manual steps:
# 1. Enter keystore password
# 2. Verify signing
# 3. Verify APK size & checksum
```

### Post-Release

1. [ ] Upload APK to GitHub Releases
2. [ ] (Optional) Upload to Google Play Store Console
3. [ ] Update social media
4. [ ] Monitor crash reports
5. [ ] Check first-hour metrics

---

## 📞 Support & Community

### For Development Questions
- **GitHub Discussions:** https://github.com/TU_USUARIO/AURA/discussions
- **Issues:** https://github.com/TU_USUARIO/AURA/issues

### For Mobile Issues
- Tag: `mobile`, `android`, `termux`
- Include: phone model, Android version, error logs
- Reproduction steps required

### Response Times
- P1 (critical): <30 minutes
- P2 (major): <2 hours
- P3 (minor): <8 hours

See [docs/SUPPORT-SLA.md](docs/SUPPORT-SLA.md) for full SLA.

---

**Last Updated:** September 2026
**Version:** v2.1.0
