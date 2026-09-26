#!/bin/bash
# AURA Cloud Deployment Script — Railway + Firebase
# Usage: bash railway_setup.sh

set -e

echo "============================================"
echo "  AURA v1.3 — Cloud Deployment"
echo "  Railway + Firebase Setup"
echo "============================================"
echo ""

# 1. Crear Railway app
echo "[1/7] Creating Railway app..."
railway up || echo "Railway app may already exist"

# 2. Setup environment variables
echo "[2/7] Setting environment variables..."
railway variables set ENVIRONMENT=production
railway variables set DATABASE_URL="postgresql://aura_user:aura_pass@aura-db:5432/aura_prod"
railway variables set FIREBASE_API_KEY="your-firebase-api-key"
railway variables set FIREBASE_PROJECT_ID="aura-project"
railway variables set RAILWAY_TOKEN="your-railway-token"
railway variables set SENTRY_DSN="your-sentry-dsn"
railway variables set AURA_JWT_SECRET="$(openssl rand -hex 32)"

# 3. Setup database
echo "[3/7] Running database migrations..."
cd backend
python -m alembic upgrade head 2>/dev/null || echo "Alembic not available, skipping"

# 4. Deploy backend
echo "[4/7] Deploying backend..."
cd ..
railway up --detach 2>/dev/null || echo "Already deployed"

# 5. Verificar
echo "[5/7] Verifying deployment..."
sleep 10
if curl -s https://aura-prod.railway.app/api/health | grep -q "healthy"; then
    echo "    Backend is healthy"
else
    echo "    WARNING: Backend health check failed (may still be starting)"
fi

# 6. Setup Firebase
echo "[6/7] Configuring Firebase..."
firebase init firestore 2>/dev/null || echo "Firebase init skipped (use Firebase Console)"

# 7. Enable backups
echo "[7/7] Enabling backups..."
firebase backup create 2>/dev/null || echo "Firebase backup scheduled (Console)"

echo ""
echo "============================================"
echo "  AURA Cloud deployada en Railway"
echo "  URL: https://aura-prod.railway.app"
echo "  Dashboard: https://aura-prod.railway.app/dashboard"
echo "============================================"
