# AURA OS v2.1 — Complete Installation Guide

Choose your platform and follow the guide. All methods are tested and documented.

## Installation Methods (Choose One)

1. **📱 Android** — Mobile app (easiest, no setup required)
2. **🐳 Docker** — Containerized (recommended for most)
3. **🖥️ Local** — Development environment
4. **☁️ Cloud** — Deploy to 7 platforms
5. **🖨️ USB Boot** — Complete Linux machine
6. **🪟 Windows** — Standalone EXE
7. **🍎 macOS** — Native binary

---

## 📱 Android Installation

### Prerequisites
- Android 11+ device
- 2GB RAM minimum
- 2GB storage available
- WiFi connection

### Steps

#### Step 1: Install App

**Option A: Google Play Store (Easiest)**
```
https://play.google.com/store/apps/details?id=com.aura.launcher
```

**Option B: Direct APK Download**
1. Visit: https://github.com/TU_USUARIO/AURA/releases/latest
2. Download: `AURA-2.1.0-signed-arm64-v8a-aligned.apk`
3. Open file → Install

**Option C: ADB (Developer)**
```bash
adb install AURA-2.1.0-signed-arm64-v8a-aligned.apk
```

#### Step 2: Initial Setup

1. Open "AURA Launcher" app
2. Grant storage permissions (required)
3. Wait for backend initialization (10-15s)
4. Select mode: Local or Remote

#### Step 3: Choose Mode

**Local Mode (Offline):**
- ✅ No internet needed
- ✅ Full Ubuntu environment
- ✅ 6 Go tools included
- ✅ All data local

```bash
# Backend auto-starts
# Access: http://localhost:8000/api/docs
```

**Remote Mode (Desktop Sync):**
- ✅ Stream desktop AURA OS
- ✅ Full system control
- ✅ Real-time sync
- ⚠️ Requires desktop + WiFi

### Troubleshooting

**App won't install?**
```bash
# Clear storage cache
adb shell pm clear com.aura.launcher
adb install AURA-*.apk
```

**Backend won't start?**
```bash
# Reinstall Termux
# Then run bootstrap in Termux app:
bash ~/.aura/scripts/termux-bootstrap.sh
```

---

## 🐳 Docker Installation

### Prerequisites
- Docker & Docker Compose installed
- 4GB RAM minimum
- Ports 8000, 6379 available

### Steps

#### Step 1: Clone Repository

```bash
git clone https://github.com/TU_USUARIO/AURA.git
cd AURA
```

#### Step 2: Configure Environment

```bash
cp .env.example .env

# Edit .env (optional - defaults work fine)
nano .env
```

#### Step 3: Start Services

```bash
# Start all services in background
docker-compose up -d

# Watch startup logs
docker-compose logs -f

# Wait for "Uvicorn running on" message
```

#### Step 4: Verify Installation

```bash
# Health check
curl http://localhost:8000/api/health
# Should return: {"status":"healthy"}

# Open API docs
open http://localhost:8000/api/docs
# or visit in browser: http://localhost:8000/api/docs
```

### Services Running

| Service | Port | Status |
|---------|------|--------|
| FastAPI Backend | 8000 | http://localhost:8000 |
| Omniroute Gateway | 8080 | http://localhost:8080 |
| Redis Cache | 6379 | localhost:6379 |
| PostgreSQL | 5432 | localhost:5432 |
| Qdrant Vectors | 6333 | localhost:6333 |

### Common Commands

```bash
# View logs
docker-compose logs -f backend

# Stop services
docker-compose down

# Reset database
docker-compose down -v  # Also removes volumes

# Rebuild images
docker-compose build --no-cache

# Access shell
docker-compose exec backend bash
```

---

## 🖥️ Local Development Installation

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+** (or SQLite for dev)
- **Redis 7+** (optional, for caching)
- **Git**

### Step 1: Clone Repository

```bash
git clone https://github.com/TU_USUARIO/AURA.git
cd AURA
```

### Step 2: Create Virtual Environment

```bash
# Python venv
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or on Windows:
venv\Scripts\activate

# Check Python version
python --version  # Should be 3.11+
```

### Step 3: Install Dependencies

```bash
cd backend

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Verify
python -c "from main import app; print('✅ Import OK')"
```

### Step 4: Database Setup

#### Using SQLite (Easiest for Dev)

```bash
# Database auto-creates in current directory
python -c "from main import app; print('✅ Ready')"
```

#### Using PostgreSQL (Recommended for Prod)

```bash
# Create database
createdb aura_db

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/aura_db

# Run migrations
alembic upgrade head
```

### Step 5: Configuration

```bash
# Copy example env
cp .env.example .env

# Edit with your settings
nano .env

# Required settings:
# ENVIRONMENT=development
# SECRET_KEY=your-secret-key
# LOG_LEVEL=DEBUG
```

### Step 6: Start Backend

```bash
# With auto-reload (development)
python -m uvicorn main:app --reload --port 8000

# Or production mode
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

### Step 7: Verify

```bash
curl http://localhost:8000/api/health
# Should return: {"status":"healthy"}

# Visit dashboard
open http://localhost:8000/api/docs
```

---

## ☁️ Cloud Deployment

### Supported Platforms (7 Options)

```bash
./scripts/deploy-platforms.sh
# Select:
# 1. Railway (Recommended - easiest)
# 2. Render
# 3. AWS Lambda
# 4. DigitalOcean
# 5. Heroku
# 6. PythonAnywhere
# 7. Self-hosted (VPS)
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed per-platform guides.

---

## 🖨️ USB Boot (Linux Machine)

### Prerequisites
- 4GB USB drive
- ~15 minutes
- Rufus (Windows) or dd (Linux/Mac)

### Steps

#### Step 1: Download ISO

```bash
# From GitHub releases
wget https://github.com/TU_USUARIO/AURA/releases/download/v2.1.0/aura-os-2.1.0.iso
```

#### Step 2: Write to USB

**Linux/Mac:**
```bash
# Find USB device
lsblk  # or diskutil list (Mac)

# Write ISO (replace sdX with your device)
sudo dd if=aura-os-2.1.0.iso of=/dev/sdX bs=4M status=progress
sudo sync
```

**Windows:**
1. Download Rufus: https://rufus.ie
2. Select ISO file
3. Select USB device
4. Click "Start"

#### Step 3: Boot

1. Insert USB drive
2. Restart computer
3. Press F12 (or DEL, ESC) at startup
4. Select USB boot option
5. Wait for Alpine Linux to load

#### Step 4: Login

```bash
# First boot asks for setup
# Then login with:
username: aura
password: aura123

# Start AURA OS
./start-aura.sh

# API available at: http://localhost:8000
```

---

## 🪟 Windows Installation

### Prerequisites
- Windows 10 or later
- 500MB storage
- Administrator access (optional)

### Steps

#### Step 1: Download Executable

```
https://github.com/TU_USUARIO/AURA/releases/download/v2.1.0/AURA-OS-2.1.0-standalone.exe
```

#### Step 2: Run Installer

1. Double-click `AURA-OS-2.1.0-standalone.exe`
2. Accept license
3. Select installation folder
4. Click "Install"
5. Finish

#### Step 3: Launch

**From Start Menu:**
- Search "AURA OS"
- Click to launch

**From Desktop:**
- Double-click "AURA OS" icon

**From Command Line:**
```bash
"C:\Program Files\AURA OS\aura-os.exe"
```

#### Step 4: Verify

```bash
# Opens web interface automatically
# API: http://localhost:8000/api/docs
```

---

## 🍎 macOS Installation

### Prerequisites
- macOS 11 or later
- 500MB storage
- Homebrew (optional)

### Steps

#### Step 1: Download Binary

**Via Homebrew (Easiest):**
```bash
brew tap TU_USUARIO/aura
brew install aura-os
```

**Manual Download:**
```
https://github.com/TU_USUARIO/AURA/releases/download/v2.1.0/AURA-OS-2.1.0-macos-universal.dmg
```

#### Step 2: Install

**Homebrew:**
```bash
brew install aura-os
aura-os  # Run
```

**Manual DMG:**
1. Double-click `.dmg` file
2. Drag "AURA OS" to Applications
3. Open Applications → AURA OS

#### Step 3: Verify

```bash
# Opens automatically in browser
# API: http://localhost:8000/api/docs
```

---

## ✅ Installation Verification Checklist

After installation, verify everything works:

```bash
# 1. Health check
curl http://localhost:8000/api/health
# Expected: {"status":"healthy"}

# 2. List providers
curl http://localhost:8000/api/providers
# Expected: JSON array of providers

# 3. Chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
# Expected: Response from AI provider

# 4. Omniroute health
curl http://localhost:8000/api/omniroute/health
# Expected: Provider status

# 5. Storage check
df -h  # Verify sufficient space remaining
```

All should return 2xx status codes (except df).

---

## 🆘 Troubleshooting Installation

### General Issues

**Port 8000 in use?**
```bash
# Find what's using port
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process or use different port
python -m uvicorn main:app --port 8001
```

**Permission denied?**
```bash
# Make scripts executable
chmod +x scripts/*.sh
chmod +x /usr/local/bin/aura-os  # If installed globally
```

**Out of storage?**
```bash
# Clean up
docker-compose down -v  # Remove volumes
pip cache purge
rm -rf ~/.cache/pip
```

### Platform-Specific

**Android:**
- Termux not installing? → Settings → Biometric → Disable
- Backend crash? → Reinstall Termux + re-run bootstrap

**Docker:**
- Cannot connect to Docker daemon? → Start Docker service
- Out of disk? → `docker system prune -a`

**Local (Python):**
- Import error? → Upgrade pip: `pip install --upgrade pip`
- Database error? → Delete db file + restart
- Port conflict? → Use: `--port 8001`

**Cloud:**
- Deployment fails? → Check build logs in platform console
- Can't access? → Verify firewall rules allow port 8000

**USB Boot:**
- Won't boot? → Re-write ISO with Rufus
- Can't login? → Check keyboard layout (QWERTY)
- No internet? → Configure WiFi in Hyprland

---

## 🔄 Updating AURA OS

### Docker

```bash
cd AURA
git pull origin master
docker-compose down
docker-compose up -d
```

### Local (Python)

```bash
git pull origin master
pip install -r backend/requirements.txt --upgrade
# Restart backend service
```

### Mobile (Android)

```bash
# Check for updates in app
# Or download latest APK from releases
adb install -r AURA-2.1.1.apk
```

### USB Boot

```bash
# Download new ISO from releases
# Re-write to USB with Rufus/dd
# Boot from USB (fresh install)
```

---

## 📊 Installation Statistics

| Method | Time | Storage | Difficulty | Best For |
|--------|------|---------|-----------|----------|
| Android | 5min | 2GB | Easy | Mobile use |
| Docker | 5min | 1GB | Easy | Development |
| Local | 10min | 500MB | Medium | Advanced dev |
| Cloud | 15min | Varies | Medium | Production |
| USB Boot | 15min | 4GB USB | Hard | Full OS |
| Windows | 5min | 500MB | Easy | Windows users |
| macOS | 5min | 500MB | Easy | Mac users |

---

## ✨ Next Steps After Installation

1. **Read Quick Start:** [QUICK-START.md](QUICK-START.md) (5 minutes)
2. **Explore API:** Visit http://localhost:8000/api/docs
3. **Try Examples:** See [docs/EXAMPLES.md](docs/EXAMPLES.md)
4. **Learn Architecture:** Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
5. **Join Community:** [GitHub Discussions](https://github.com/TU_USUARIO/AURA/discussions)

---

**Need Help?**

- 📖 [Troubleshooting](docs/TROUBLESHOOTING.md)
- 💬 [GitHub Discussions](https://github.com/TU_USUARIO/AURA/discussions)
- 🐛 [Report Issues](https://github.com/TU_USUARIO/AURA/issues)
- 📧 Email: hello@aura.local

---

**Last Updated:** September 2026
