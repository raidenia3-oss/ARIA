#!/bin/bash

# AURA OS Post-Release Monitoring

set -e

GITHUB_REPO="${GITHUB_REPO:-$(git config --get remote.origin.url 2>/dev/null | sed -E 's#.*github.com[:/]([^/]*/[^/]+)(\.git)?$#\1#' || true)}"
GITHUB_REPO="${GITHUB_REPO:-unknown/AURA}"
RELEASE_TAG="${RELEASE_TAG:-v2.1.0}"
WEBHOOK_URL="${DISCORD_WEBHOOK:-}"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS v2.1.0 Release Monitoring                     ║"
echo "╚════════════════════════════════════════════════════════╝"

# Monitor GitHub Release
echo "[*] Checking GitHub release status..."

RELEASE_DATA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO/releases/tags/$RELEASE_TAG")

DOWNLOADS=$(echo "$RELEASE_DATA" | grep -o '"download_count": [0-9]*' | head -1 | grep -o '[0-9]*')
STARS=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO" | grep '"stargazers_count"' | grep -o '[0-9]*')

FORKS=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO" | grep '"forks_count"' | grep -o '[0-9]*')

ISSUES=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO/issues?state=open" | grep -c '"id"' || echo "0")

echo "[+] Release Statistics:"
echo "    Downloads: $DOWNLOADS"
echo "    Stars: $STARS"
echo "    Forks: $FORKS"
echo "    Open Issues: $ISSUES"

# Monitor CI/CD pipeline
echo ""
echo "[*] Checking CI/CD pipeline status..."

WORKFLOW_STATUS=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$GITHUB_REPO/actions/runs" | \
  grep -o '"status": "[^"]*"' | head -1 | grep -o '[^"]*"$' | tr -d '"')

echo "[+] Latest workflow: $WORKFLOW_STATUS"

# Monitor Docker image
echo ""
echo "[*] Checking Docker image builds..."

DOCKER_IMAGE="ghcr.io/$GITHUB_REPO/aura:v2.1.0"

echo "[*] Docker image: $DOCKER_IMAGE"
echo "[*] Pull: docker pull $DOCKER_IMAGE"

# Send metrics to Discord (optional)
if [ -n "$WEBHOOK_URL" ]; then
    curl -X POST "$WEBHOOK_URL" \
      -H 'Content-Type: application/json' \
      -d "{
        \"embeds\": [{
          \"title\": \"AURA OS v2.1.0 Release Metrics\",
          \"fields\": [
            {\"name\": \"STARS\", \"value\": \"$STARS\", \"inline\": true},
            {\"name\": \"FORKS\", \"value\": \"$FORKS\", \"inline\": true},
            {\"name\": \"DOWNLOADS\", \"value\": \"$DOWNLOADS\", \"inline\": true},
            {\"name\": \"ISSUES\", \"value\": \"$ISSUES\", \"inline\": true},
            {\"name\": \"CI/CD\", \"value\": \"$WORKFLOW_STATUS\", \"inline\": true}
          ],
          \"color\": 16711680
        }]
      }"
fi

# Generate report
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Report Generated: $(date)"
echo "╚════════════════════════════════════════════════════════╝"

cat > RELEASE_METRICS.md << EOF
# AURA OS v2.1.0 Release Metrics

Generated: $(date)

## GitHub Statistics
- Stars: $STARS
- Forks: $FORKS
- Downloads: $DOWNLOADS
- Open Issues: $ISSUES

## CI/CD Status
- Latest Workflow: $WORKFLOW_STATUS
- Docker Image: $DOCKER_IMAGE

## Action Items
- [ ] Monitor social media mentions
- [ ] Respond to issues
- [ ] Track community feedback
- [ ] Plan v2.2 based on feedback

---
Updated: $(date)
EOF

echo "[+] Report saved to RELEASE_METRICS.md"
