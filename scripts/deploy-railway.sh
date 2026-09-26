#!/bin/bash

# Deploy AURA to Railway.app

set -e

echo "Deploying AURA to Railway..."

# Install Railway CLI if not present
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    npm install -g @railway/cli
fi

# Login to Railway
railway login

# Create new project
railway init

# Set environment variables
railway variable set ENVIRONMENT=production
railway variable set PYTHON_VERSION=3.10
railway variable set AURA_PORT=8000

# Link to GitHub
echo "Linking to GitHub repository..."
railway link

# Deploy
echo "Deploying..."
railway up

echo "✓ Deployment complete!"
echo "Your app is live at: $(railway domains)"
