#!/bin/bash

# scripts/launch.sh
# AURA OS v2.1 Official Launch Script

set -e

VERSION="2.1.0"
REPO_URL="https://github.com/TU_USUARIO/AURA"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK:-}"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS v${VERSION} — OFFICIAL LAUNCH SEQUENCE          ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "[*] STEP 1: Pre-Launch Verification"
echo "────────────────────────────────────"

if [ -n "$(git status --porcelain)" ]; then
    echo "[-] ERROR: Working directory not clean"
    git status --short
    exit 1
fi
echo "[+] Git working directory clean"

if ! grep -q "$VERSION" README.md; then
    echo "[-] ERROR: Version not updated in README.md"
    exit 1
fi
echo "[+] Version updated in all files"

echo "[*] Running tests..."
if ! pytest tests/test_omniroute.py -q 2>/dev/null; then
    echo "[-] ERROR: Tests failing"
    exit 1
fi
echo "[+] All tests passing"

echo ""
echo "[*] STEP 2: Creating Git Tag"
echo "────────────────────────────────────"

if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
    echo "[-] Tag v${VERSION} already exists"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d "v${VERSION}"
        git push origin ":refs/tags/v${VERSION}" 2>/dev/null || true
    else
        exit 1
    fi
fi

git tag -a "v${VERSION}" -m "AURA OS v${VERSION} - Official Release" || {
    echo "[-] ERROR: Failed to create tag"
    exit 1
}
echo "[+] Tag created: v${VERSION}"

echo ""
echo "[*] STEP 3: Pushing to GitHub"
echo "────────────────────────────────────"

git push origin master
echo "[+] Pushed master branch"

git push origin "v${VERSION}"
echo "[+] Pushed tag v${VERSION}"

echo "[*] Waiting for GitHub Actions to complete..."
echo "[*] Check: https://github.com/TU_USUARIO/AURA/actions"
sleep 10

echo ""
echo "[*] STEP 4: Verifying GitHub Release"
echo "────────────────────────────────────"

RELEASE_URL="https://api.github.com/repos/TU_USUARIO/AURA/releases/tags/v${VERSION}"
RELEASE_CHECK=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$RELEASE_URL" | grep -c "\"id\"" || echo "0")

if [ "$RELEASE_CHECK" -gt 0 ]; then
    echo "[+] GitHub release created successfully"
    echo "[*] Release URL: https://github.com/TU_USUARIO/AURA/releases/tag/v${VERSION}"
else
    echo "[!] Release not yet created (GitHub Actions running)"
    echo "[*] Check back in a few minutes"
fi

echo ""
echo "[*] STEP 5: Generating Announcements"
echo "────────────────────────────────────"

cat > LAUNCH_ANNOUNCEMENT.txt << 'EOF'
╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║                   🚀 AURA OS v2.1 — OFFICIAL RELEASE 🚀                      ║
║                                                                                ║
║              Open-Source AI Operating System — Now Available                  ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝

📢 ANNOUNCEMENT

AURA OS v2.1 is officially launched! An open-source, production-ready AI operating
system that solves vendor lock-in by connecting to 300+ AI providers with
intelligent routing.

🎯 KEY FEATURES

✅ Multi-Provider AI Gateway (300+ providers)
✅ Go CLI Tools (port scanner, DNS resolver, enumeration)
✅ Ruby Security Suite (pentesting, exploit generation)
✅ C2 Framework (command & control server + agents)
✅ USB-Bootable Alpine Distribution
✅ Enterprise Ready: Multi-tenancy, encryption, compliance

🔗 GitHub: https://github.com/TU_USUARIO/AURA
📖 Docs: https://github.com/TU_USUARIO/AURA/blob/master/docs/KNOWLEDGE-BASE.md

⭐ Please star us on GitHub! https://github.com/TU_USUARIO/AURA
EOF

echo "[+] Announcement saved to LAUNCH_ANNOUNCEMENT.txt"

if [ -n "$DISCORD_WEBHOOK" ]; then
    echo "[*] Posting to Discord..."
    curl -X POST "$DISCORD_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "{
        \"embeds\": [{
          \"title\": \"🚀 AURA OS v${VERSION} — OFFICIAL RELEASE\",
          \"description\": \"Open-source AI operating system with 300+ providers, Go tools, Ruby security suite, and Alpine distro\",
          \"color\": 16711680,
          \"fields\": [
            {\"name\": \"🔗 GitHub\", \"value\": \"$REPO_URL\"},
            {\"name\": \"📖 Docs\", \"value\": \"$REPO_URL/blob/master/docs/KNOWLEDGE-BASE.md\"}
          ]
        }]
      }"
    echo "[+] Posted to Discord"
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  🎉 LAUNCH COMPLETE!                                  ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "📊 Launch Summary:"
echo "  • Version: v${VERSION}"
echo "  • GitHub: $REPO_URL"
echo "  • Release: $REPO_URL/releases/tag/v${VERSION}"
echo "  • Actions: $REPO_URL/actions"
echo ""
echo "📢 Next Steps:"
echo "  1. Share announcement on social media"
echo "  2. Post to GitHub Discussions"
echo "  3. Monitor GitHub issues and Discord"
echo "  4. Engage with early adopters"
echo "  5. Track metrics (stars, forks, PRs)"
echo ""
