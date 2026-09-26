#!/bin/bash

# Deploy AURA to Render.com

set -e

echo "Deploying AURA to Render..."

# Check if Procfile exists
if [ ! -f Procfile ]; then
    echo "Creating Procfile..."
    cat > Procfile << 'EOF'
web: python backend/main.py --host 0.0.0.0 --port $PORT
EOF
fi

# Check if render.yaml exists
if [ ! -f render.yaml ]; then
    echo "Creating render.yaml..."
    cat > render.yaml << 'EOF'
services:
  - type: web
    name: aura-os
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python backend/main.py --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.10
      - key: ENVIRONMENT
        value: production
EOF
fi

# Push to GitHub
git add .
git commit -m "Deploy to Render"
git push origin main

echo "✓ Pushed to GitHub"
echo "Go to render.com and connect your GitHub repository"
