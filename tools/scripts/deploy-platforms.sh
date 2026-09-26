#!/bin/bash

# AURA OS Multi-Platform Deployment Automation

set -euo pipefail

AURA_VERSION="2.1.0"
GITHUB_REPO="${GITHUB_REPO:-$(git config --get remote.origin.url 2>/dev/null | sed -E 's#.*github.com[:/]([^/]*/[^/]+)(\.git)?$#\1#' || true)}"
GITHUB_REPO="${GITHUB_REPO:-unknown/AURA}"

# ============== PLATFORM DEPLOYMENTS ==============

deploy_pythonanywhere() {
  echo "[*] Deploying to PythonAnywhere..."
  
  read -p "Enter PythonAnywhere API token: " PA_TOKEN
  read -p "Enter PythonAnywhere username: " PA_USER
  
  curl -X POST \
    https://www.pythonanywhere.com/api/v0/user/$PA_USER/webapps/ \
    -H "Authorization: Token $PA_TOKEN" \
    -d "domain_name=${PA_USER}.pythonanywhere.com"
  
  echo "[+] WebApp created on PythonAnywhere"
  echo "[*] Next steps:"
  echo "    1. Clone repo: git clone https://github.com/$GITHUB_REPO"
  echo "    2. Install deps: pip install -r requirements.txt"
  echo "    3. Configure WSGI in dashboard"
  echo "    4. Access: https://${PA_USER}.pythonanywhere.com"
}

deploy_railway() {
  echo "[*] Deploying to Railway..."
  
  if ! command -v railway &> /dev/null; then
    echo "[-] Railway CLI not found. Installing..."
    npm install -g @railway/cli
  fi
  
  railway login
  railway init
  
  echo "[*] Setting environment variables..."
  : "${DATABASE_URL:?Set DATABASE_URL before deploying to Railway}"
  : "${REDIS_URL:?Set REDIS_URL before deploying to Railway}"
  : "${OMNIROUTE_URLS:?Set OMNIROUTE_URLS before deploying to Railway}"
  railway variable set DATABASE_URL "$DATABASE_URL"
  railway variable set REDIS_URL "$REDIS_URL"
  railway variable set OMNIROUTE_URLS "$OMNIROUTE_URLS"
  
  railway up
  
  echo "[+] Deployment to Railway complete!"
  echo "[*] Access: $(railway domain)"
}

deploy_render() {
  echo "[*] Deploying to Render..."
  
  cat > render.yaml << EOF
services:
  - type: web
    name: aura-backend
    runtime: python
    startCommand: "gunicorn backend.main:app"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
    
  - type: pserv
    name: aura-postgres
    ipAllowList: []
    plan: starter
    
  - type: pserv
    name: aura-redis
    ipAllowList: []
    plan: starter

staticSite:
  name: aura-frontend
  buildCommand: "npm run build"
  publishPath: "frontend/build"
EOF

  echo "[+] render.yaml created"
  echo "[*] Deploy via Render dashboard:"
  echo "    1. Connect GitHub repo"
  echo "    2. Select this render.yaml"
  echo "    3. Deploy!"
}

deploy_aws_lambda() {
  echo "[*] Deploying to AWS Lambda (serverless)..."
  
  if ! command -v aws &> /dev/null; then
    echo "[-] AWS CLI not found. Install it first."
    exit 1
  fi
  
  : "${AWS_LAMBDA_ROLE_ARN:?Set AWS_LAMBDA_ROLE_ARN before deploying to AWS}"
  cat > "$TMP_DIR/lambda_handler.py" << 'EOF'
import json
import sys
sys.path.insert(0, '/var/task')

from backend.main import app
from mangum import Mangum

handler = Mangum(app)

def lambda_handler(event, context):
    return handler(event, context)
EOF

  pip install -r backend/requirements.txt -t "$TMP_DIR/package/"
  cp -r backend "$TMP_DIR/package/"
  cp "$TMP_DIR/lambda_handler.py" "$TMP_DIR/package/"
  
  (cd "$TMP_DIR/package" && zip -r "$TMP_DIR/aura-lambda.zip" .)
  
  aws lambda create-function \
    --function-name aura-backend-v2-1 \
    --runtime python3.11 \
    --role "$AWS_LAMBDA_ROLE_ARN" \
    --handler lambda_handler.lambda_handler \
    --zip-file fileb://aura-lambda.zip \
    --timeout 60 \
    --memory-size 512
  
  echo "[*] Creating API Gateway..."
  aws apigateway create-rest-api \
    --name aura-api \
    --description "AURA OS v2.1 API"
  
  echo "[+] Lambda deployment complete!"
}

deploy_digitalocean() {
  echo "[*] Deploying to DigitalOcean App Platform..."
  
  cat > app.yaml << 'EOF'
name: aura-os
services:
- name: backend
  github:
    repo: ${GITHUB_REPO}
    branch: master
  build_command: pip install -r backend/requirements.txt
  run_command: gunicorn -w 4 -b 0.0.0.0:8080 backend.main:app
  http_port: 8080
  envs:
  - key: DATABASE_URL
    type: VAR
  - key: REDIS_URL
    type: VAR

databases:
- name: postgres
  engine: PG
  version: "15"
- name: redis
  engine: REDIS
  version: "7"
EOF

  echo "[+] app.yaml created"
  echo "[*] Deploy via DigitalOcean dashboard or CLI:"
  echo "    doctl apps create --spec app.yaml"
}

deploy_heroku() {
  echo "[*] Deploying to Heroku (legacy)..."
  
  if ! command -v heroku &> /dev/null; then
    echo "[-] Heroku CLI not found. Install it first."
    exit 1
  fi
  
  heroku login
  
  cat > Procfile << 'EOF'
web: gunicorn -w 4 -b 0.0.0.0:$PORT backend.main:app
worker: celery -A backend.tasks worker --loglevel=info
EOF

  heroku create aura-os-v2-1
  heroku buildpacks:add heroku/python
  git push heroku master
  
  echo "[+] Deployment to Heroku complete!"
}

deploy_selfhosted() {
  echo "[*] Deploying to self-hosted server..."
  
  read -p "Enter server IP/hostname: " SERVER_HOST
  read -p "Enter SSH user: " SSH_USER
  read -p "Enter deployment path (e.g., /opt/aura): " DEPLOY_PATH
  
  cat > "$TMP_DIR/deploy-selfhosted.sh" << 'EOF'
#!/bin/bash
set -euo pipefail
DEPLOY_PATH="${1:?deployment path is required}"

echo "[*] Deploying AURA OS to $DEPLOY_PATH..."

cd $DEPLOY_PATH
git pull origin master

pip install -r backend/requirements.txt

python backend/alembic/versions/*.py

sudo systemctl restart aura

curl http://localhost:8000/api/health

echo "[+] Deployment complete!"
EOF

  chmod +x "$TMP_DIR/deploy-selfhosted.sh"
  
  scp "$TMP_DIR/deploy-selfhosted.sh" "$SSH_USER@$SERVER_HOST:$DEPLOY_PATH/"
  ssh "$SSH_USER@$SERVER_HOST" "cd '$DEPLOY_PATH' && bash deploy-selfhosted.sh '$DEPLOY_PATH'"
  
  echo "[+] Self-hosted deployment complete!"
  echo "[*] Access: http://$SERVER_HOST:8000"
}

# Keep generated deployment helpers out of the repository.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# ============== MAIN ==============

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS v${AURA_VERSION} — Deployment Automation        ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "Select deployment platform:"
echo "1) PythonAnywhere (recommended for beginners)"
echo "2) Railway (recommended for production)"
echo "3) Render (free tier available)"
echo "4) AWS Lambda (serverless)"
echo "5) DigitalOcean (VPS)"
echo "6) Heroku (legacy)"
echo "7) Self-hosted (local/VPS)"
echo ""

read -p "Enter choice (1-7): " PLATFORM

case $PLATFORM in
  1)
    deploy_pythonanywhere
    ;;
  2)
    deploy_railway
    ;;
  3)
    deploy_render
    ;;
  4)
    deploy_aws_lambda
    ;;
  5)
    deploy_digitalocean
    ;;
  6)
    deploy_heroku
    ;;
  7)
    deploy_selfhosted
    ;;
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

# ============== POST-DEPLOYMENT ==============

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Post-Deployment Checks                               ║"
echo "╚════════════════════════════════════════════════════════╝"

if [[ "${RUN_LOCAL_CHECKS:-0}" == "1" ]]; then
  sleep 5
  echo "[*] Checking API health..."
  curl --fail --silent http://localhost:8000/api/health
  echo "[+] API is healthy"
else
  echo "[*] Skipping local checks (set RUN_LOCAL_CHECKS=1 to enable them)."
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Deployment Complete!                                 ║"
echo "╚════════════════════════════════════════════════════════╝"

echo ""
echo "Next steps:"
echo "  1. Monitor logs: Check deployment platform logs"
echo "  2. Setup SSL: Use Let's Encrypt for HTTPS"
echo "  3. Configure firewall: Allow ports 80, 443"
echo "  4. Setup backups: Daily backups of database"
echo "  5. Monitor performance: Use provided monitoring scripts"
