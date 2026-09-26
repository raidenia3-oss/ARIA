#!/bin/bash
# AURA OS — Mobile Development Helper
# For iterative development of the Flutter launcher and Termux integration

set -euo pipefail

LAUNCHER_DIR="aura-os/mobile-launcher"
DEVICE_STATUS="unknown"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "AURA OS Mobile - Dev Helper"
    echo ""
    echo "Usage: bash scripts/dev-mobile.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build     - Build debug APK (quick, no signing)"
    echo "  watch     - Hot reload mode (requires connected device)"
    echo "  test      - Build debug + install on connected device"
    echo "  termux    - Open Termux shell in Ubuntu 22.04"
    echo "  logs      - Stream backend logs from device"
    echo "  device    - Check if device is connected"
    echo "  lint      - Run flutter analyze"
    echo "  sync      - Test backend mobile sync actions"
    echo "  all       - Full dev cycle: lint + build + test"
    echo ""
    echo "Options:"
    echo "  --device <id>  Specify device ID (adb devices)"
    echo "  --help         Show this help"
}

# Parse arguments
COMMAND="${1:-help}"
DEVICE_ID="${2:-}"

if [ "$COMMAND" = "--help" ] || [ "$COMMAND" = "-h" ]; then
    usage
    exit 0
fi

# Check if we're in the right directory
if [ ! -d "$LAUNCHER_DIR" ]; then
    echo -e "${RED}[-] Error: $LAUNCHER_DIR not found${NC}"
    echo "This script must be run from the AURA project root"
    exit 1
fi

# ============== Common functions ==============

check_flutter() {
    if ! command -v flutter > /dev/null 2>&1; then
        echo -e "${RED}[-] Error: Flutter SDK not found${NC}"
        echo "[*] Install: https://flutter.dev/docs/get-started/install"
        return 1
    fi
    return 0
}

check_adb() {
    if ! command -v adb > /dev/null 2>&1; then
        echo -e "${RED}[-] Error: ADB not found${NC}"
        echo "[*] Install: Android SDK platform-tools"
        return 1
    fi
    return 0
}

check_device() {
    if ! check_adb; then
        return 1
    fi

    if [ -n "$DEVICE_ID" ]; then
        adb -s "$DEVICE_ID" shell echo "Device OK" 2>/dev/null || {
            echo -e "${RED}[-] Error: Device $DEVICE_ID not found${NC}"
            return 1
        }
    else
        local count
        count=$(adb devices 2>/dev/null | grep -c "device$" || echo "0")
        if [ "$count" -eq 0 ]; then
            echo -e "${YELLOW}[!] No device connected${NC}"
            echo "[*] Connect device and enable USB debugging"
            return 1
        elif [ "$count" -gt 1 ]; then
            echo -e "${YELLOW}[!] Multiple devices connected. Use --device <id>${NC}"
            adb devices
            return 1
        fi
    fi

    DEVICE_STATUS="connected"
    return 0
}

# ============== Commands ==============

cmd_lint() {
    echo -e "${YELLOW}[*] Running Flutter analyze...${NC}"
    if check_flutter; then
        cd "$LAUNCHER_DIR"
        flutter analyze 2>&1 || {
            echo -e "${YELLOW}[!] Lint warnings found (non-blocking)${NC}"
        }
        echo -e "${GREEN}[+] Lint complete${NC}"
        cd - > /dev/null
    else
        echo -e "${YELLOW}[!] Flutter not installed - skipping lint${NC}"
        echo "[*] Tip: Install Flutter to enable full lint checking"
    fi
}

cmd_build() {
    echo -e "${YELLOW}[*] Building debug APK...${NC}"
    if check_flutter; then
        cd "$LAUNCHER_DIR"
        flutter build apk --debug --split-per-abi 2>&1 || {
            echo -e "${RED}[-] Build failed${NC}"
            cd - > /dev/null
            return 1
        }

        echo -e "${GREEN}[+] Debug APK built:${NC}"
        for apk in build/app/outputs/apk/debug/*-release.apk; do
            if [ -f "$apk" ]; then
                echo "  $(basename $apk) ($(du -h "$apk" | cut -f1))"
            fi
        done
        cd - > /dev/null
    else
        echo -e "${RED}[-] Flutter not installed${NC}"
        exit 1
    fi
}

cmd_test() {
    echo -e "${YELLOW}[*] Building and installing on device...${NC}"

    if ! check_device; then
        echo -e "${RED}[-] No device connected${NC}"
        echo "[*] Run 'bash scripts/dev-mobile.sh build' instead"
        exit 1
    fi

    if ! check_flutter; then
        exit 1
    fi

    cd "$LAUNCHER_DIR"

    echo "[*] Building debug APK..."
    flutter build apk --debug --split-per-abi 2>&1

    echo "[*] Installing on device..."
    for apk in build/app/outputs/apk/debug/*-release.apk; do
        if [ -f "$apk" ]; then
            echo "[*] Installing $(basename $apk)..."
            adb "$DEVICE_ID" install -r "$apk"
        fi
    done

    echo -e "${GREEN}[+] Installed on device${NC}"
    echo "[*] Launch from app drawer or:"
    echo "  adb $DEVICE_ID shell am start -n com.aura.launcher/.MainActivity"

    cd - > /dev/null
}

cmd_watch() {
    echo -e "${YELLOW}[*] Starting hot reload mode...${NC}"

    if ! check_flutter; then
        exit 1
    fi

    if ! check_device; then
        echo -e "${YELLOW}[!] No device connected. Using emulator or skip.${NC}"
        echo "[*] Tip: Run 'flutter emulators --create' first"
        echo "[*] Or connect USB device with debugging enabled"
    fi

    cd "$LAUNCHER_DIR"
    echo "[*] Running flutter run..."
    echo "[*] Press 'r' for hot reload, 'R' for restart, 'q' to quit"
    flutter run 2>&1
    cd - > /dev/null
}

cmd_termux() {
    echo -e "${YELLOW}[*] Opening Termux shell...${NC}"

    if ! check_device; then
        echo -e "${RED}[-] No device connected${NC}"
        exit 1
    fi

    local adb_prefix=""
    [ -n "$DEVICE_ID" ] && adb_prefix="-s $DEVICE_ID"

    echo "[*] Entering Ubuntu 22.04 in Termux..."
    echo "[*] Type 'exit' twice to return"

    adb $adb_prefix shell 2>/dev/null || true
}

cmd_logs() {
    echo -e "${YELLOW}[*] Streaming backend logs...${NC}"

    if ! check_device; then
        echo "[*] No device connected. Showing local backend logs..."
        tail -f /tmp/aura.log 2>/dev/null || echo "[!] No log file at /tmp/aura.log"
        exit 0
    fi

    local adb_prefix=""
    [ -n "$DEVICE_ID" ] && adb_prefix="-s $DEVICE_ID"

    echo "[*] Streaming logs from device..."
    echo "[*] Press Ctrl+C to stop"

    adb $adb_prefix logcat 2>/dev/null | grep -i "aura\|flutter\|termux" | head -50
}

cmd_device() {
    echo -e "${YELLOW}[*] Checking connected devices...${NC}"

    if ! check_adb; then
        exit 1
    fi

    echo "[*] Connected devices:"
    adb devices

    local count
    count=$(adb devices 2>/dev/null | grep -c "device$" || echo "0")

    if [ "$count" -eq 1 ]; then
        echo -e "${GREEN}[+] One device connected${NC}"
    elif [ "$count" -gt 1 ]; then
        echo -e "${YELLOW}[!] Multiple devices: use --device <id>${NC}"
    else
        echo -e "${RED}[-] No device connected${NC}"
    fi
}

cmd_sync() {
    echo -e "${YELLOW}[*] Testing backend mobile sync actions...${NC}"

    if ! [ -d "backend" ]; then
        echo -e "${RED}[-] backend/ directory not found${NC}"
        exit 1
    fi

    PYTHONPATH=. python3 -c "
import asyncio
from backend.mobile.sync import SyncManager

async def test():
    sm = SyncManager()

    tests = [
        ('ping', {}),
        ('get_system_info', None),
        ('get_mode', None),
        ('get_settings', None),
    ]

    for action, data in tests:
        payload = {'action': action}
        if data:
            payload['data'] = data
        result = await sm.sync_data(None, payload)
        status = 'OK' if result.get('status') == 'ok' else 'FAIL'
        print(f'  [{status}] {action}: {result.get(\"status\", \"unknown\")}')

asyncio.run(test())
" 2>/dev/null || {
        echo -e "${RED}[-] Sync test failed${NC}"
        echo "[*] Make sure backend dependencies are installed"
    }
}

cmd_all() {
    echo -e "${BLUE}=== Full Development Cycle ===${NC}"
    echo ""

    echo "[1/4] Linting..."
    cmd_lint
    echo ""

    echo "[2/4] Building debug APK..."
    cmd_build
    echo ""

    echo "[3/4] Testing sync actions..."
    cmd_sync
    echo ""

    echo "[4/4] Device check..."
    cmd_device
    echo ""

    if check_device; then
        echo "[+] Optionally run: bash scripts/dev-mobile.sh test"
        echo "[+] Or for hot reload: bash scripts/dev-mobile.sh watch"
    fi

    echo ""
    echo -e "${GREEN}=== Development cycle complete ===${NC}"
}

# ============== Main ==============

case "$COMMAND" in
    build)   cmd_build ;;
    watch)   cmd_watch ;;
    test)    cmd_test ;;
    termux)  cmd_termux ;;
    logs)    cmd_logs ;;
    device)  cmd_device ;;
    lint)    cmd_lint ;;
    sync)    cmd_sync ;;
    all)     cmd_all ;;
    help|--help|-h) usage ;;
    *)
        echo -e "${RED}[-] Unknown command: $COMMAND${NC}"
        usage
        exit 1
        ;;
esac
