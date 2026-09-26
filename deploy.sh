#!/bin/bash
set -e

echo "=========================================="
echo "  AURA Auto Deploy - Fly.io"
echo "=========================================="
echo ""

# Check flyctl
if ! command -v flyctl &> /dev/null; then
    echo "ERROR: flyctl not found. Install from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Login check
if ! flyctl auth whoami &> /dev/null; then
    echo "Please login to Fly.io first:"
    flyctl auth login
fi

echo "[1/5] Creating backend app..."
flyctl apps create aura-backend || true

echo "[2/5] Creating model volume..."
flyctl volumes create aura_models --size 2 --region iad || true

echo "[3/5] Setting secrets..."
flyctl secrets set AURA_API_KEY="${AURA_API_KEY:-dev-key-change-me}"
flyctl secrets set GEMINI_API_KEY="${GEMINI_API_KEY:-}"
flyctl secrets set GROQ_API_KEY="${GROQ_API_KEY:-}"
flyctl secrets set OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
flyctl secrets set AURA_LOCAL_MODEL_PATH="/app/models/qwen-0.5b"

echo "[4/5] Deploying backend..."
cd backend
flyctl deploy

echo "[5/5] Getting URL..."
BACKEND_URL=$(flyctl info --json | grep -o '"Hostname":"[^"]*"' | cut -d'"' -f4)
echo ""
echo "=========================================="
echo "  Backend deployed!"
echo "  URL: https://$BACKEND_URL"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test: curl https://$BACKEND_URL/health"
echo "2. Deploy Discord bot: cd services/discord-bot && flyctl deploy"
echo "3. Build Android: open dist/Build_Android.bat"
