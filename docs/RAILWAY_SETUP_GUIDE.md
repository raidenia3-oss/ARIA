# Railway Deployment Guide v3.0

Complete step-by-step setup for deploying AURA/AME backend to Railway.

> **Commands validated against the current Railway CLI.** Use `--json` where
> shown and prefer `railway up` (it signs you in and deploys in one shot).

---

## Prerequisites

### 1. Install Railway CLI

```bash
# macOS
brew install railway

# Linux / WSL
npm install -g @railway/cli

# Windows
winget install Railway

# Verify
railway --version
# Should show: v3.x.x or higher
```

### 2. Create Railway Account

1. Go to https://railway.app
2. Sign up (GitHub recommended)
3. Create new project

### 3. Local Setup

```bash
# Clone repo
git clone https://github.com/raidenia3-oss/AURA-server.01.git
cd AURA-server.01

# Verify backend files exist
ls -la backend/
# Should show: main.py, requirements.txt

# Verify railway config
cat railway.toml
# Should show: [deploy] with buildCommand / startCommand / healthcheckPath
```

---

## Step 1: Login to Railway

```bash
railway login
# Browser opens, authorize GitHub
# Returns: "✓ Logged in"

# Verify
railway whoami
# Shows your Railway username
```

> Tip: `railway up` also self-validates auth and will sign you up/in if needed.

---

## Step 2: Create Railway Project

```bash
# Create + link a new project in one step
railway init --name aura-backend

# (Optional) If you prefer to link an existing project instead:
# railway link --project <project-id-or-name>
```

---

## Step 3: Add Database

Railway provides PostgreSQL automatically.

```bash
# Add a managed Postgres database (always pass --json for scripting)
railway add --database postgres --json
# Output: {"serviceId":"...","serviceName":"..."}

# DATABASE_URL is created automatically as a project variable.
# Read it back with:
railway variable list --json | jq -r '.[] | select(.name=="DATABASE_URL") | .value'
```

> Always list existing services (`railway service list --json`) before adding,
> to avoid creating a duplicate database.

---

## Step 4: Set Environment Variables

```bash
# Via CLI
railway variable set JWT_SECRET "$(openssl rand -base64 32)"
railway variable set BRIDGE_SECRET "$(openssl rand -base64 32)"
railway variable set QWEN_URL "https://your-huggingface-space-url"
railway variable set GEMINI_API_KEY "your-google-ai-key"
railway variable set VERCEL_TOKEN "your-vercel-token"  # For CI/CD

# Verify
railway variable list --json | jq -r '.[] | "\(.name)=\(.value)"'
```

> `DATABASE_URL` is created by the Postgres service in Step 3 — do not set it
> manually. The helper `scripts/setup-railway.sh` does both steps for you.

---

## Step 5: Configure Health Check

Railway reads the health check from `railway.toml`:

```toml
[deploy]
healthcheckPath = "/api/health"
healthcheckTimeout = 100
```

If not auto-detected, set it in the Railway dashboard → Service settings →
Health Check URL: `/api/health`.

---

## Step 6: Deploy

### Option A: Via CLI (Recommended)

```bash
# From repo root
railway up

# Shows:
# • Building...
# • Uploading...
# • Deploying...
# • ✓ Deployment complete

# Get public URL
railway domain
# Output: https://aura-backend-prod-abc123.railway.app

# Test endpoint
curl https://aura-backend-prod-abc123.railway.app/api/health
# Should return: {"ok": true, ...}
```

> Never report a deploy as successful without a terminal `SUCCESS`. After
> `railway up --detach`, poll `railway deployment list --json` until the newest
> deployment status is `SUCCESS`.

### Option B: Via GitHub (Auto-deploy)

```bash
# Push to main
git push origin main

# Railway auto-detects and deploys (if railway.toml present)

# Check status
railway logs
```

---

## Step 7: Connect Frontend to Backend

In `frontend/.env.local` (or Vercel project settings):

```
NEXT_PUBLIC_API_BASE=https://aura-backend-prod-abc123.railway.app
```

Then the frontend will POST to:
```
https://aura-backend-prod-abc123.railway.app/api/webhooks
```

---

## Step 8: Monitor Deployment

### View Logs

```bash
railway logs --follow          # real-time
railway logs --service backend # filter by service
railway logs --until 1h        # historical
```

### Check Health

```bash
curl https://aura-backend-prod-abc123.railway.app/api/health

# Database connection (inside the container)
railway run python -c "import psycopg2; print('DB OK')"
```

### Metrics

Railway dashboard → Service → shows CPU, memory, network I/O, deploy history.

---

## Troubleshooting

### Deploy Fails: "No main.py found"

```bash
ls -la backend/main.py          # must exist
cat railway.toml                # must have a [deploy] build/start
railway up --detach             # re-deploy and poll deployment list
```

### Endpoint Returns 503

```bash
railway logs                    # check why the process exited
# Common: DATABASE_URL not set, port not $PORT, import error
railway up --detach
```

### Health Check Timeout

```bash
# Test locally
uvicorn backend.main:app --port 8000
curl http://localhost:8000/api/health
```

### Database Connection Error

```bash
railway variable list --json | jq -r '.[] | select(.name=="DATABASE_URL") | .value'
# If missing, re-add:
railway add --database postgres --json
```

---

## Scaling

Railway dashboard → Service → Instance Size:
- Memory: 512MB (default) → 1GB / 2GB
- CPU: Shared → Dedicated

```bash
railway service scale   # set min/max replicas for auto-scaling
```

---

## Cost Estimation

Railway pricing (approx):
- Compute: ~$0.000463/hour (≈ $3.40/month per GB)
- Database: $5–15/month
- Bandwidth: $0.10/GB outbound

**Estimate for AURA backend:** ~$18–23/month. See https://railway.app/pricing.

---

## Production Checklist

- [ ] Environment variables set (JWT_SECRET, BRIDGE_SECRET, QWEN_URL, GEMINI_API_KEY, VERCEL_TOKEN)
- [ ] DATABASE_URL present (from Postgres service)
- [ ] Health check returning 200 (`/api/health`)
- [ ] Database connected successfully
- [ ] Logs show no errors
- [ ] Frontend points to correct backend URL
- [ ] SSL certificate auto-generated (Railway handles this)
- [ ] Database backups enabled (Railway automatic 24h backups)

---

## Next Steps

1. **Monitor Logs** (first 24h): `railway logs --follow`
2. **Test Integrations**:
   ```bash
   curl -X POST https://your-backend.railway.app/api/news/recommend \
     -H "Content-Type: application/json" \
     -d '{"topic":"AI"}'
   ```
3. **Set Up Alerts** (Railway dashboard → Notifications)
4. **Schedule Backups** (Railway auto-backups; manual: `railway db export`)

---

## Resources

- Railway Docs: https://docs.railway.app
- CLI Reference: `railway --help`
- GitHub Integration: https://railway.app/github

---

**Good luck! 🚀**
