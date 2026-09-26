#!/bin/bash

# AURA OS v2.0 — Deployment Script
# Uso: bash scripts/deploy.sh [environment]

set -e  # Exit on error

ENVIRONMENT="${1:-development}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       AURA OS v2.0 — Deployment Script                        ║"
echo "║       Environment: $ENVIRONMENT                                ║"
echo "║       Timestamp: $TIMESTAMP                                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ════════════════════════════════════════════════════════════════════════════
# 1. Pre-flight checks
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[1/5] Running pre-flight checks...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 not found${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}ERROR: Git not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Git${NC}"

# Check .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ .env not found, creating from .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠ Edit .env with your configuration${NC}"
fi

echo ""

# ════════════════════════════════════════════════════════════════════════════
# 2. Setup environment
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[2/5] Setting up environment...${NC}"

# Create directories
mkdir -p data logs

# Create venv if not exists
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel --quiet

echo -e "${GREEN}✓ Environment setup complete${NC}"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# 3. Install dependencies
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[3/5] Installing dependencies...${NC}"

if [ "$ENVIRONMENT" = "production" ]; then
    pip install -r requirements-prod.txt --quiet
else
    pip install -r requirements.txt --quiet
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# 4. Database setup
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[4/5] Running database setup...${NC}"

# Create auth tables
python3 << 'EOF'
from backend.database import Base, engine
from backend.auth.models import User, Session

Base.metadata.create_all(bind=engine)
print("✓ Database tables created")
EOF

echo ""

# ════════════════════════════════════════════════════════════════════════════
# 5. Compile & validate
# ════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[5/5] Validating installation...${NC}"

# py_compile check
python3 -m py_compile backend/main.py
python3 -m py_compile backend/auth/__init__.py
python3 -m py_compile backend/auth/models.py
python3 -m py_compile backend/auth/service.py

echo -e "${GREEN}✓ All modules compile successfully${NC}"

# ════════════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗"
echo "║      ✅ AURA OS v2.0 Deployment Complete                     ║"
echo "╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your configuration"
echo "  2. Start server: python backend/main.py"
echo "  3. Open http://localhost:8000"
echo ""
