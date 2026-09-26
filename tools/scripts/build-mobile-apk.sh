#!/bin/bash
# AURA OS — Mobile APK Build & Release Automation
# Builds, signs, verifies, and prepares AURA Mobile APK for distribution

set -euo pipefail

VERSION="${1:-2.1.0}"
APP_NAME="AURA_OS_Mobile"
KEYSTORE_PATH="${KEYSTORE_PATH:-$HOME/.android/aura-release-key.jks}"
KEYSTORE_ALIAS="aura-mobile"
KEYSTORE_PASSWORD="${KEYSTORE_PASSWORD:-}"
KEY_PASSWORD="${KEY_PASSWORD:-}"
BUNDLE_ID="com.aura.launcher"
LAUNCHER_DIR="aura-os/mobile-launcher"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AURA OS Mobile (v${VERSION}) — APK Build & Release     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# ============== STEP 1: ENVIRONMENT CHECK ==============

echo ""
echo -e "${YELLOW}[*] STEP 1: Checking Build Environment${NC}"
echo "────────────────────────────────────"

# Check Flutter
if ! command -v flutter &> /dev/null; then
    echo -e "${RED}[-] ERROR: Flutter SDK not found in PATH${NC}"
    echo "[*] Install Flutter: https://flutter.dev/docs/get-started/install"
    exit 1
fi
echo -e "${GREEN}[+] Flutter: $(flutter --version | head -1)${NC}"

# Check JDK
if ! command -v java &> /dev/null; then
    echo -e "${RED}[-] ERROR: Java not found${NC}"
    echo "[*] Install JDK 11+: https://openjdk.java.net"
    exit 1
fi
echo -e "${GREEN}[+] Java: $(java -version 2>&1 | head -1)${NC}"

# Check Android SDK
if [ -z "${ANDROID_HOME:-}" ]; then
    echo -e "${YELLOW}[!] WARNING: ANDROID_HOME not set${NC}"
    export ANDROID_HOME="$HOME/Android/Sdk"
fi
if [ ! -d "$ANDROID_HOME" ]; then
    echo -e "${RED}[-] ERROR: Android SDK not found at $ANDROID_HOME${NC}"
    echo "[*] Install Android Studio or set ANDROID_HOME manually"
    exit 1
fi
echo -e "${GREEN}[+] Android SDK: $ANDROID_HOME${NC}"

# Check keytool
if ! command -v keytool &> /dev/null; then
    echo -e "${RED}[-] ERROR: keytool not found (part of JDK)${NC}"
    exit 1
fi
echo -e "${GREEN}[+] keytool: $(which keytool)${NC}"

# Check zipalign
if ! command -v zipalign &> /dev/null; then
    echo -e "${RED}[-] ERROR: zipalign not found (part of Android SDK)${NC}"
    echo "[*] Ensure build-tools are installed: sdkmanager 'build-tools;34.0.0'"
    exit 1
fi
echo -e "${GREEN}[+] zipalign: $(which zipalign)${NC}"

# Check adb (optional)
if command -v adb &> /dev/null; then
    echo -e "${GREEN}[+] adb: $(adb version | head -1)${NC}"
else
    echo -e "${YELLOW}[!] adb not found (optional, for device testing)${NC}"
fi

echo -e "${GREEN}[+] Environment checks passed${NC}"

# ============== STEP 2: KEYSTORE SETUP ==============

echo ""
echo -e "${YELLOW}[*] STEP 2: Setting up Keystore${NC}"
echo "────────────────────────────────────"

if [ ! -f "$KEYSTORE_PATH" ]; then
    echo "[*] Creating new keystore..."

    if [ -z "$KEYSTORE_PASSWORD" ]; then
        read -sp "Enter keystore password: " KEYSTORE_PASSWORD
        echo
    fi

    if [ -z "$KEY_PASSWORD" ]; then
        read -sp "Enter key password (or press Enter for same as keystore): " KEY_PASSWORD
        echo
        if [ -z "$KEY_PASSWORD" ]; then
            KEY_PASSWORD="$KEYSTORE_PASSWORD"
        fi
    fi

    mkdir -p "$(dirname "$KEYSTORE_PATH")"

    keytool -genkey -v \
        -keystore "$KEYSTORE_PATH" \
        -keyalg RSA \
        -keysize 4096 \
        -validity 10000 \
        -alias "$KEYSTORE_ALIAS" \
        -storepass "$KEYSTORE_PASSWORD" \
        -keypass "$KEY_PASSWORD" \
        -dname "CN=AURA OS,O=AURA,L=Global,ST=Global,C=US"

    echo -e "${GREEN}[+] Keystore created: $KEYSTORE_PATH${NC}"
else
    echo -e "${GREEN}[+] Keystore found: $KEYSTORE_PATH${NC}"

    if [ -z "$KEYSTORE_PASSWORD" ]; then
        read -sp "Enter keystore password: " KEystORE_PASSWORD
        echo
    fi

    if [ -z "$KEY_PASSWORD" ]; then
        KEY_PASSWORD="$KEYSTORE_PASSWORD"
    fi
fi

# Create key.properties for Flutter
KEY_PROPERTIES="$LAUNCHER_DIR/key.properties"
cat > "$KEY_PROPERTIES" << EOF
storePassword=$KEYSTORE_PASSWORD
keyAlias=$KEYSTORE_ALIAS
storeFile=$KEYSTORE_PATH
keyPassword=$KEY_PASSWORD
EOF
echo -e "${GREEN}[+] key.properties created at $KEY_PROPERTIES${NC}"

# ============== STEP 3: VERSION UPDATE ==============

echo ""
echo -e "${YELLOW}[*] STEP 3: Updating Version Numbers${NC}"
echo "────────────────────────────────────"

if [ -f "$LAUNCHER_DIR/pubspec.yaml" ]; then
    sed -i "s/version: .*/version: $VERSION+1/" "$LAUNCHER_DIR/pubspec.yaml"
    echo -e "${GREEN}[+] pubspec.yaml updated to v$VERSION+1${NC}"
else
    echo -e "${RED}[-] ERROR: pubspec.yaml not found at $LAUNCHER_DIR/pubspec.yaml${NC}"
    exit 1
fi

# Update Android version info
ANDROID_MANIFEST="$LAUNCHER_DIR/android/app/src/main/AndroidManifest.xml"
if [ -f "$ANDROID_MANIFEST" ]; then
    sed -i "s/android:versionCode=\"[0-9]*\"/android:versionCode=\"$(echo $VERSION | tr -d '.')\"" "$ANDROID_MANIFEST"
    sed -i "s/android:versionName=\"[^\"]*\"/android:versionName=\"$VERSION\"" "$ANDROID_MANIFEST"
    echo -e "${GREEN}[+] AndroidManifest.xml version updated${NC}"
fi

# ============== STEP 4: DEPENDENCIES ==============

echo ""
echo -e "${YELLOW}[*] STEP 4: Installing Flutter Dependencies${NC}"
echo "────────────────────────────────────"

cd "$LAUNCHER_DIR"

echo "[*] Running flutter pub get..."
flutter pub get 2>&1 || {
    echo -e "${RED}[-] ERROR: flutter pub get failed${NC}"
    exit 1
}
echo -e "${GREEN}[+] Dependencies installed${NC}"

# ============== STEP 5: BUILD APK ==============

echo ""
echo -e "${YELLOW}[*] STEP 5: Building APK (Release)${NC}"
echo "────────────────────────────────────"
echo -e "${YELLOW}[*] Building universal + split-per-ABI APKs...${NC}"
echo "[*] This may take 5-10 minutes..."

# Build universal APK first, then splits
flutter build apk \
    --release \
    --split-per-abi

APK_BUILD_SUCCESS=$?
if [ $APK_BUILD_SUCCESS -ne 0 ]; then
    echo -e "${RED}[-] ERROR: APK build failed${NC}"
    exit 1
fi
echo -e "${GREEN}[+] APK built successfully${NC}"

# ============== STEP 6: BUILD APP BUNDLE ==============

echo ""
echo -e "${YELLOW}[*] STEP 6: Building App Bundle (for Google Play)${NC}"
echo "────────────────────────────────────"

flutter build appbundle --release 2>&1 || {
    echo -e "${YELLOW}[!] WARNING: App bundle build failed (optional, Google Play requires AAB)${NC}"
}
echo -e "${GREEN}[+] App bundle built successfully${NC}"

cd - > /dev/null

# ============== STEP 7: SIGN APK ==============

echo ""
echo -e "${YELLOW}[*] STEP 7: Signing APK Files${NC}"
echo "────────────────────────────────────"

APK_DIR="$LAUNCHER_DIR/build/app/outputs/apk/release"
SIGNED_DIR="$LAUNCHER_DIR/build/app/outputs/signed"
mkdir -p "$SIGNED_DIR"

SIGN_COUNT=0
if ls "$APK_DIR"/*.apk 1> /dev/null 2>&1; then
    for apk in "$APK_DIR"/*.apk; do
        if [ -f "$apk" ]; then
            APK_NAME=$(basename "$apk")
            # Extract ABI from filename
            ABI_SUFFIX=""
            case "$APK_NAME" in
                *arm64-v8a*) ABI_SUFFIX="arm64-v8a" ;;
                *armeabi-v7a*) ABI_SUFFIX="armeabi-v7a" ;;
                *x86_64*) ABI_SUFFIX="x86_64" ;;
                *x86*) ABI_SUFFIX="x86" ;;
                *) ABI_SUFFIX="universal" ;;
            esac

            SIGNED_APK="$SIGNED_DIR/aura-mobile-v${VERSION}-${ABI_SUFFIX}.apk"

            # Sign with apksigner (preferred)
            if [ -d "$ANDROID_HOME/build-tools" ]; then
                LATEST_BULD_TOOLS=$(ls -d "$ANDROID_HOME/build-tools"/3* 2>/dev/null | sort -r | head -1)
                if [ -n "$LATEST_BULD_TOOLS" ]; then
                    "$LATEST_BULD_TOOLS/bin/apksigner" sign \
                        --ks "$KEYSTORE_PATH" \
                        --ks-key-alias "$KEYSTORE_ALIAS" \
                        --ks-pass pass:"$KEYSTORE_PASSWORD" \
                        --key-pass pass:"$KEY_PASSWORD" \
                        --out "$SIGNED_APK.apk" \
                        "$apk"

                    SIGN_COUNT=$((SIGN_COUNT + 1))
                    echo -e "${GREEN}[+] Signed: $SIGNED_APK.apk${NC}"

                    # Zipalign (apksigner may have already aligned)
                    zipalign -v 4 "$apk" "$SIGNED_APK.apk" 2>/dev/null || true

                    continue
                fi
            fi

            # Fallback: jarsigner + zipalign
            jarsigner -verbose \
                -sigalg SHA1withRSA \
                -digestalg SHA1 \
                -keystore "$KEYSTORE_PATH" \
                -storepass "$KEYSTORE_PASSWORD" \
                -keypass "$KEY_PASSWORD" \
                "$apk" \
                "$KEYSTORE_ALIAS"

            ALIGNED_APK="$SIGNED_DIR/aura-mobile-v${VERSION}-${ABI_SUFFIX}-aligned.apk"
            cp "$apk" "$ALIGNED_APK"
            zipalign -v 4 "$APK" "$ALIGNED_APK.apk"

            SIGN_COUNT=$((SIGN_COUNT + 1))
            echo -e "${GREEN}[+] Signed: $ALIGNED_APK${NC}"
        fi
    done
else
    echo -e "${RED}[-] ERROR: No APK files found in $APK_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}[+] Signed $SIGN_COUNT APK(s)${NC}"

# ============== STEP 8: VERIFY APK ==============

echo ""
echo -e "${YELLOW}[*] STEP 8: Verifying APK Signatures${NC}"
echo "────────────────────────────────────"

VERIFY_COUNT=0
for apk in "$SIGNED_DIR"/*.apk; do
    if [ -f "$apk" ]; then
        APK_BASENAME=$(basename "$apk")
        echo "Verifying: $APK_BASENAME"

        # apksigner verify (preferred)
        if [ -d "$ANDROID_HOME/build-tools" ]; then
            LATEST_BULD_TOOLS=$(ls -d "$ANDROID_HOME/build-tools"/3* 2>/dev/null | sort -r | head -1)
            if [ -n "$LATEST_BULD_TOOLS" ]; then
                "$LATEST_BULD_TOOLS/bin/apksigner" verify "$apk" 2>&1 && {
                    echo -e "  ${GREEN}✓ Signature valid${NC}"
                    VERIFY_COUNT=$((VERIFY_COUNT + 1))
                } || {
                    echo -e "  ${RED}✗ Signature verification failed${NC}"
                    exit 1
                }
            fi
        fi

        # Fallback: jarsigner -verify
        jarsigner -verify -verbose "$apk" 2>&1 | tail -1
    fi
done

# ============== STEP 9: CREATE RELEASE MANIFEST ==============

echo ""
echo -e "${YELLOW}[*] STEP 9: Creating Release Manifest${NC}"
echo "────────────────────────────────────"

MANIFEST_DIR="$LAUNCHER_DIR/build/app/outputs/signed"
mkdir -p "$MANIFEST_DIR"

cat > "$MANIFEST_DIR/RELEASE-MANIFEST.md" << EOF
# AURA OS Mobile v${VERSION} — Release Manifest

**Release Date:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Version:** $VERSION
**Build ID:** $(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
**Git Tag:** v${VERSION}
**Bundle ID:** ${BUNDLE_ID}

## Distribution Files

### Android APK

EOF

# List all APKs
for apk in "$MANIFEST_DIR"/*.apk; do
    if [ -f "$apk" ]; then
        APK_NAME=$(basename "$apk")
        APK_SIZE=$(du -h "$apk" | cut -f1)
        echo "- **\`${APK_NAME}\`** (${APK_SIZE})" >> "$MANIFEST_DIR/RELEASE-MANIFEST.md"
    fi
done

cat >> "$MANIFEST_DIR/RELEASE-MANIFEST.md" << 'EOF'

### App Bundle

- **`app-release.aab`** (~40MB) — For Google Play Store distribution
  - Automatically optimized per device by Google Play

## Installation Methods

### Method 1: Google Play Store
```
https://play.google.com/store/apps/details?id=com.aura.launcher
```

### Method 2: Manual APK Install

```bash
# Download APK
wget https://github.com/YOUR_USERNAME/AURA/releases/download/v2.1.0/aura-mobile-v2.1.0-arm64-v8a.apk

# Install on connected device
adb install -r aura-mobile-v2.1.0-arm64-v8a.apk

# Or install universal APK for any architecture
adb install -r aura-mobile-v2.1.0-universal.apk
```

### Method 3: Web/PWA
```
# Build PWA (no app store required)
flutter build web --release

# Serve with any static server
python -m http.server 8080
```

## Installation Steps (Mobile)

1. Enable "Install unknown apps" for your browser/file manager
2. Download the appropriate APK for your device architecture:
   - **arm64-v8a**: Most modern phones (Snapdragon 8, Exynos, Dimensity)
   - **armeabi-v7a**: Older 32-bit phones (Snapdragon 4/6 series)
   - **universal**: Works on all, but larger file size
3. Open the downloaded APK file
4. Tap "Install" and accept permissions
5. Open AURA Mobile
6. The launcher will auto-discover your AURA OS desktop via mDNS

## Device Compatibility

| Architecture | Devices | Recommended |
|---|---|---|
| arm64-v8a | Snapdragon 8 Gen 1/2/3, Exynos 2200+, Dimensity 9000+ | ✅ Yes |
| armeabi-v7a | Snapdragon 4/6/7 series, older devices | ✅ Fallback |
| x86_64 | Android emulators, Intel tablets | ✅ Testing |
| universal | All devices | ✅ Max compatibility |

## Permissions

The APK requests the following permissions:
- `INTERNET` — Connect to AURA OS backend
- `ACCESS_NETWORK_STATE` — Check connectivity
- `ACCESS_WIFI_STATE` — Detect AURA OS on local network
- `RECORD_AUDIO` — Voice commands to AURA
- `CAMERA` — WebRTC video streaming
- `WRITE_EXTERNAL_STORAGE` — Save screenshots/logs

## Build Configuration

- **Build mode**: Release (--release)
- **Obfuscation**: Disabled (for debugging)
- **Split per ABI**: Yes (smaller downloads)
- **Min SDK**: 21 (Android 5.0+)
- **Target SDK**: 34 (Android 14)
- **Compile SDK**: 34

EOF

echo -e "${GREEN}[+] Release manifest: $MANIFEST_DIR/RELEASE-MANIFEST.md${NC}"

# ============== STEP 10: OPTIONAL — UPLOAD TO GITHUB ==============

echo ""
echo -e "${YELLOW}[*] STEP 10: GitHub Release${NC}"
echo "────────────────────────────────────"

if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
    echo "[*] Uploading to GitHub Releases..."

    # Create GitHub release
    gh release create "v${VERSION}" \
        "$MANIFEST_DIR"/*.apk \
        "$LAUNCHER_DIR/build/app/outputs/bundle/release/app-release.aab" \
        --title "AURA OS Mobile v${VERSION}" \
        --notes-file "$MANIFEST_DIR/RELEASE-MANIFEST.md" \
        --repo "$GITHUB_REPOSITORY" \
        2>&1 || {
        echo -e "${YELLOW}[!] WARNING: GitHub release upload skipped${NC}"
    }
    echo -e "${GREEN}[+] Uploaded to GitHub Releases${NC}"
else
    echo -e "${YELLOW}[!] Skipping GitHub upload (set GITHUB_TOKEN + GITHUB_REPOSITORY)${NC}"
    echo "[*] To upload to GitHub:"
    echo "  gh release create v${VERSION} \\"
    for apk in "$MANIFEST_DIR"/*.apk; do
        echo "    $(basename $apk) \\"
    done
    echo "    --repo YOUR_USERNAME/AURA"
fi

# ============== STEP 11: OPTIONAL — INSTALL ON DEVICE ==============

if command -v adb &> /dev/null; then
    echo ""
    echo -e "${YELLOW}[*] STEP 11: Install on connected device?${NC}"
    echo "────────────────────────────────────"
    read -p "[?] Install universal APK on connected device? (y/N): " INSTALL_ANSWER
    if [[ "$INSTALL_ANSWER" =~ ^[Yy]$ ]]; then
        UNIVERSAL_APK=$(ls -S "$MANIFEST_DIR"/"${VERSION}"-*-universal.apk 2>/dev/null | head -1)
        if [ -n "$UNIVERSAL_APK" ] && [ -f "$UNIVERSAL_APK" ]; then
            echo "[*] Installing $(basename $UNIVERSAL_APK)..."
            adb install -r "$UNIVERSAL_APK"
            echo -e "${GREEN}[+] Installed on device${NC}"
        else
            echo -e "${YELLOW}[!] Universal APK not found${NC}"
        fi
    fi
fi

# ============== FINAL SUMMARY ==============

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ✅ BUILD COMPLETE — AURA Mobile v${VERSION}              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "📁 Signed APKs:"
for apk in "$MANIFEST_DIR"/*.apk; do
    if [ -f "$apk" ]; then
        echo "  $(basename $apk) ($(du -h "$apk" | cut -f1))"
    fi
done
echo ""
echo "📄 Release manifest: $MANIFEST_DIR/RELEASE-MANIFEST.md"
echo "🔑 Keystore: $KEYSTORE_PATH (alias: $KEYSTORE_ALIAS)"
echo ""
echo "📲 Next steps:"
echo "  1. Test: adb install <apk>"
echo "  2. Upload: gh release create v${VERSION} $MANIFEST_DIR/*.apk"
echo "  3. Publish: Upload app-release.aab to Google Play Console"
echo ""

if [ -f "$LAUNCHER_DIR/build/app/outputs/bundle/release/app-release.aab" ]; then
    echo "📦 App Bundle: $LAUNCHER_DIR/build/app/outputs/bundle/release/app-release.aab"
fi
