# AURA OS Mobile (AME) — Improvement Plan

Research-backed improvements based on 6 similar open-source projects (Re-TUI, termux-launcher, Deep Thought, V-Launcher, Synco, EcoBridge, Lilypad).

---

## 🔍 Research Findings

### Projects Analyzed

| Project | Language | Key Strengths | Lessons for AME |
|---|---|---|---|
| **Re-TUI** | Kotlin | Command-first launcher, Termux bridges | `tbridge` pattern for Termux comms |
| **termux-launcher** (PickleHik3) | Kotlin/Java | Termux as home screen, sixel rendering | Terminal-first with app launching |
| **Deep Thought** | Flutter | Rich Flutter structure, Termux bootstrap | `shell/`, `providers/`, `services/` pattern |
| **V-Launcher** | Kotlin/Compose | Local Ollama LLM, Termux lifecycle mgmt | Kill/restart Termux for socket cleanliness |
| **Synco** | Kotlin/Compose | Android↔desktop sync, wakeup service | Foreground service, exponential backoff, AES-256-GCM |
| **EcoBridge** | Flutter | Device bridge via mDNS+WebSocket+WebRTC | Zero-config discovery, E2E encryption |
| **Lilypad** | Tauri/RN | Remote control via WebRTC, QR pairing | Public internet streaming |

### Key Patterns from Research

1. **Termux Lifecycle Management** (V-Launcher)
   - `pkill -9 -f ollama` before starting backend
   - Prevents socket conflicts and stale processes
   - Manages Termux RUN_COMMAND permission

2. **Foreground Service + Wake Lock** (Synco)
   - Keeps WebSocket alive when screen off
   - 4-minute wake lock refresh
   - Auto-reconnect with exponential backoff

3. **mDNS Discovery + Manual IP Fallback** (EcoBridge, Synco)
   - Zero-config device discovery
   - Fallback to manual IP entry
   - Auto-accept private IP ranges (10.x, 172.x, 192.168.x)

4. **Dual-Stack Connectivity** (Synco)
   - Works over WiFi router OR phone hotspot
   - Desktop auto-detects connection type

5. **Local LLM Integration** (V-Launcher)
   - Ollama runs in Termux
   - qwen2.5:0.5b for resource efficiency
   - Offline operation fully supported

---

## 🚧 Current State Assessment

### What AME Has ✅

| Component | Status | Source |
|---|---|---|
| Flutter launcher (`main.dart`) | ✅ Extended with TermuxService, ModeToggle | FASE 14 |
| WebSocket sync (`/ws/mobile/sync`) | ✅ Existing in `backend/main.py:2184` | FASE 14 |
| REST mobile endpoints | ✅ `/api/mobile/mode`, `/api/mobile/termux/cmd` | FASE 14 |
| Sync actions (sync.py) | ✅ get_system_info, execute_termux, get_mode | FASE 14 |
| Termux bootstrap script | ✅ `scripts/termux-bootstrap.sh` | FASE 14 |
| Cross-compile Go tools | ✅ `scripts/cross-compile-go-tools.sh` | FASE 14 |
| APK build automation | ✅ `scripts/build-mobile-apk.sh` | FASE 15 |
| Dev helper script | ✅ `scripts/dev-mobile.sh` | FASE 17 |
| Architecture docs | ✅ `docs/MOBILE-ARCHITECTURE.md` | FASE 14 |
| Dev workflow docs | ✅ `docs/MOBILE-DEV-WORKFLOW.md` | FASE 17 |

### ❌ Critical Gaps

| Gap | Risk | Solution (from research) |
|---|---|---|
| **No `android/` directory** | ⚠️ Cannot build APK (gradle/manifest missing) | Create Flutter Android project structure |
| **No foreground service** | ⚠️ Sync disconnects when screen off | Implement foreground service (Synco pattern) |
| **No Termux lifecycle mgmt** | ⚠️ Socket conflicts on resume | Kill/restart backend (V-Launcher pattern) |
| **No local LLM** | ⚠️ Requires internet for AI | Install Ollama in Termux |
| **No crash reporting** | ⚠️ Silent failures | Add error boundaries + logging |
| **No background reconnect** | ⚠️ Disconnects not recovered | Exponential backoff (Synco pattern) |
| **pubspec.yaml lacks mobile deps** | ⚠️ Missing camera, WebRTC | Add flutter_webrtc, permission_handler |
| **No runtime permissions** | ⚠️ Android 11+ restrictions | Add permission_handler + handlers |
| **No battery optimization bypass** | ⚠️ Android kills app | Request ignore battery optimizations |
| **No push notifications** | ⚠️ No background wake | Add firebase_messaging (or local) |

---

## 📋 Improvement Roadmap

### Tier 1 — Critical (Must fix before mobile release)

#### 1. Create Android Project Structure

**Problem:** `aura-os/mobile-launcher/` only has `lib/` and `pubspec.yaml` — no `android/` directory, no gradle, no manifest. Cannot build APK.

**Solution:**
```bash
cd aura-os/mobile-launcher
flutter create .  # Regenerates android/ ios/ web/ directories
```

**Files needed:**
- `android/app/build.gradle` — Build config
- `android/app/src/main/AndroidManifest.xml` — Permissions
- `android/gradle.properties` — Build settings
- `android/build.gradle` — Project-level config

**Minimum permissions for AndroidManifest.xml:**
```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" /> <!-- for WiFi discovery -->
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
```

#### 2. Update pubspec.yaml with Mobile Dependencies

**Current pubspec.yaml:**
```yaml
dependencies:
  flutter:
    sdk: flutter
  web_socket_channel: ^2.4.0
  http: ^1.2.0
  provider: ^6.1.0
  flutter_local_notifications: ^17.0.0
  mdns_plugin: ^2.0.0
  shared_preferences: ^2.2.0
  cupertino_icons: ^1.0.6
```

**Add (research-backed):**
```yaml
dependencies:
  # Existing...
  flutter_webrtc: ^0.11.0        # WebRTC streaming (from flutter-webrtc)
  permission_handler: ^11.3.0    # Runtime permissions
  battery_plus: ^2.1.0           # Battery optimization awareness
  connectivity_plus: ^5.0.0      # Network state detection
  termux: ^1.0.0                 # Termux integration (or use intent)
  flutter_foreground_task: ^6.0.0  # Foreground service for sync
  workmanager: ^0.5.0             # Background tasks
```

#### 3. Add Foreground Service for Persistent Sync

**Pattern from Synco:** Foreground service with wake lock, 4-min refresh.

**Implementation:**
```dart
// lib/services/background_sync.dart
class BackgroundSyncService {
  static const _channel = AndroidNotificationDetails(
    'aura_sync',
    'AURA Sync',
    channelDescription: 'Mantiene conexión con AURA OS desktop',
    importance: AndroidNotificationImportance.low,
  );

  Future<void> startForegroundService() async {
    // Start foreground service
    // Keep WebSocket alive
    // 4-min wake lock refresh
  }
}
```

#### 4. Termux Lifecycle Management

**Pattern from V-Launcher:** Kill/restart Termux processes before starting backend.

**Implementation:**
```dart
// In TermuxService, before startLocalBackend():
await runCommand("pkill -f 'python.*main.py' || true");
await runCommand("sleep 1 && proot-distro login ubuntu-22.04 -- python3 /opt/aura/backend/main.py &");
```

### Tier 2 — High Priority (Important improvements)

#### 5. Local LLM via Ollama in Termux

**Pattern from V-Launcher:** Ollama runs in Termux with small model (qwen2.5:0.5b).

```bash
# In termux-bootstrap.sh:
pkg install -y proot-distro
proot-distro install ubuntu-22.04
proot-distro login ubuntu-22.04

# Inside Ubuntu:
apt install -y curl
curl -fsSL https://ollama.com/install.sh | sh
ollama run qwen2.5:0.5b  # 0.5GB model for mobile
```

#### 6. Background Reconnect with Exponential Backoff

```dart
// Upgrade connection retry in main.dart
class ConnectionManager {
  Timer? _reconnectTimer;
  int _attemptCount = 0;
  static const int _maxDelaySec = 300;

  void scheduleReconnect() {
    final delay = pow(2, _attemptCount).toInt().clamp(1, _maxDelaySec);
    _reconnectTimer = Timer(Duration(seconds: delay), connect);
    _attemptCount++;
  }
}
```

#### 7. Crash Reporting + Error Boundaries

```dart
// Add error boundaries
FlutterError.onError = (FlutterErrorDetails details) {
  // Log to local file
  // Send to backend if remote mode
};
```

### Tier 3 — Medium Priority (Enhancements)

#### 8. Battery Optimization Whitelist

```dart
// Check battery optimization on resume
if (await PowerManager.isIgnoringBatteryOptimizations == false) {
  // Prompt user to whitelist
}
```

#### 9. Dual Connectivity (WiFi + Hotspot)

```dart
// Allow connection over hotspot
// Synco pattern: desktop auto-accepts 192.168.x.x and 10.x.x.x
```

#### 10. Push Notifications for Remote Mode

```bash
# Add to pubspec.yaml:
# firebase_messaging: ^14.0.0
```

### Tier 4 — Nice-to-have

#### 11. WebRTC Screen Capture
Using `flutter_webrtc` — screen streaming from desktop to phone.

#### 12. PiP Mode
Picture-in-picture for remote desktop stream.

#### 13. App Widgets
Native Android widgets for quick AURA actions.

#### 14. iOS Support
Requires different approach (no Termux on iOS). Use remote mode only.

---

## 🛠️ Implementation Plan (Prioritized)

| # | Task | Effort | Priority | Blockers |
|---|---|---|---|---|
| 1 | Create android/ directory | 2 min | 🔴 Critical | None |
| 2 | Update pubspec.yaml | 5 min | 🔴 Critical | None |
| 3 | Add permissions to manifest | 3 min | 🔴 Critical | #1 |
| 4 | Foreground service | 30 min | 🔴 Critical | #2 |
| 5 | Termux lifecycle mgmt | 20 min | 🔴 Critical | #3 |
| 6 | Local Ollama in Termux | 45 min | 🟡 High | Termux packages |
| 7 | Reconnect w/ backoff | 30 min | 🟡 High | #4 |
| 8 | Crash reporting | 20 min | 🟡 High | #2 |
| 9 | Battery optimization | 15 min | 🟡 High | #2 |
| 10 | Firebase messaging | 20 min | 🟢 Medium | Firebase account |
| 11 | WebRTC screen capture | 60 min | 🟢 Medium | #2, #4 |
| 12 | PiP mode | 30 min | 🟢 Medium | #11 |

---

## 📋 Quick Wins (Ready to implement)

### 1. Fix android/ directory (5 min)
```bash
cd aura-os/mobile-launcher
flutter create .
git add android/
```

### 2. Update pubspec.yaml (5 min)
Add: flutter_webrtc, permission_handler, connectivity_plus, battery_plus

### 3. Add permissions (3 min)
Edit `android/app/src/main/AndroidManifest.xml`

### 4. Upgrade reconnect logic (30 min)
Improve existing auto-reconnect in main.dart with exponential backoff

### 5. Termux cleanup (20 min)
Add `pkill` before starting backend in TermuxService

---

## 📚 References

- [Re-TUI](https://github.com/DvilSpawn/Re-TUI) — Termux-first launcher
- [termux-launcher](https://github.com/PickleHik3/termux-launcher) — Termux as home screen
- [Deep Thought Terminal](https://github.com/iceqing/deep-thought-terminal) — Flutter terminal emulator
- [V-Launcher](https://github.com/vertigo0628/V-launcher) — Local Ollama + Termux lifecycle
- [Synco](https://github.com/dhruvesh07/Synco) — Android/desktop sync with wake lock
- [EcoBridge](https://explore.market.dev/ecosystems/flutter/projects/ecobridge) — Device bridge architecture
- [Lilypad](https://github.com/Kush402/lilypad) — WebRTC remote control
- [flutter-webrtc](https://github.com/flutter-webrtc/flutter-webrtc) — WebRTC for Flutter

---

## 🎯 Next Steps (Recommended Order)

1. **Fix Critical Gaps First** (android/, pubspec.yaml, permissions)
2. **Add foreground service** for persistent sync
3. **Upgrade Termux bootstrap** with Ollama + lifecycle management
4. **Add error boundaries** and crash reporting
5. **Test on physical device** (emulator insufficient for Termux)

---

**Last Updated:** September 2026
**Research Date:** September 3, 2026
**Status:** Ready for implementation
