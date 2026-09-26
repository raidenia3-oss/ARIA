#!/bin/bash

# AURA OS Release Script
# Usage: ./scripts/release.sh v2.1.0

set -e

VERSION=${1:-}

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v2.1.0"
    exit 1
fi

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS Release: $VERSION"
echo "╚════════════════════════════════════════════════════════╝"

# Step 1: Validate version format
if ! [[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "[-] Invalid version format. Use: v<major>.<minor>.<patch>"
    exit 1
fi

VERSION_NUM=${VERSION#v}

echo "[*] Step 1: Validating version format..."
echo "[+] Version: $VERSION"

# Step 2: Check git status
echo "[*] Step 2: Checking git status..."

if [ -n "$(git status --porcelain)" ]; then
    echo "[-] Working directory is not clean"
    echo "Uncommitted changes:"
    git status --short
    exit 1
fi

echo "[+] Working directory is clean"

# Step 3: Update version in files
echo "[*] Step 3: Updating version numbers..."

# backend/__init__.py
sed -i "s/__version__ = .*/\__version__ = \"$VERSION_NUM\"/" backend/__init__.py

# README.md
sed -i "s/version: .*/version: $VERSION_NUM/" README.md

# Dockerfile
sed -i "s/AURA_VERSION=.*/AURA_VERSION=$VERSION_NUM/" aura-os/distro-builder/Dockerfile

echo "[+] Version numbers updated"

# Step 4: Run tests
echo "[*] Step 4: Running tests..."

python -m pytest tests/ -q || {
    echo "[-] Tests failed. Not proceeding with release."
    exit 1
}

echo "[+] All tests passed"

# Step 5: Build artifacts
echo "[*] Step 5: Building artifacts..."

mkdir -p release/

# Go tools
cd aura-os/go-tools
make clean
make build
cp -r bin/* ../../release/
cd ../../

# Generate checksums
cd release
sha256sum * > CHECKSUMS.txt
cd ..

echo "[+] Artifacts built"

# Step 6: Create git tag
echo "[*] Step 6: Creating git tag..."

git add backend/__init__.py README.md aura-os/distro-builder/Dockerfile
git commit -m "Release: $VERSION"
git tag -a "$VERSION" -m "AURA OS $VERSION Release"

echo "[+] Git tag created: $VERSION"

# Step 7: Prepare release notes
echo "[*] Step 7: Generating release notes..."

cat > CHANGELOG_ENTRY.md << EOF
# $VERSION ($(date +%Y-%m-%d))

## Major Features
- Omniroute integration (300+ AI providers)
- Go tooling suite (networking, C2, etc)
- Ruby security tools (penetration testing)
- Alpine USB distribution
- Hyprland desktop environment

## Bug Fixes
- Fixed FastAPI forward-ref resolution
- Fixed Pydantic model_ids warning
- Fixed auth service imports

## Performance
- Improved scanner performance (65k ports < 30s)
- Optimized C2 beaconing (< 100ms latency)
- Reduced container size (155MB)

## Contributors
- Raiden (Architecture)
- Kilo (Implementation)

---

[Full Changelog](https://github.com/your-repo/aura/blob/master/CHANGELOG.md)
EOF

cat CHANGELOG_ENTRY.md

# Step 8: Push to GitHub
echo "[*] Step 8: Pushing to GitHub..."

read -p "Push to GitHub? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin master
    git push origin "$VERSION"
    echo "[+] Pushed to GitHub"
else
    echo "[!] Skipped GitHub push"
fi

# Step 9: Summary
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Release Complete!"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. GitHub Actions will create release"
echo "  2. Docker image will be published"
echo "  3. Documentation will be deployed"
echo ""
echo "Release artifacts in: ./release/"
echo ""
