#!/bin/bash
set -e

echo "🚀 Setting up AURA development environment..."

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Install backend-specific dependencies
if [ -f "backend/requirements.txt" ]; then
    echo "📦 Installing backend dependencies..."
    pip install -r backend/requirements.txt
fi

# Install HF Space dependencies
if [ -f "hf-space/requirements.txt" ]; then
    echo "📦 Installing HF Space dependencies..."
    pip install -r hf-space/requirements.txt
fi

# Install Node.js dependencies for frontend
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Install Ruby dependencies for Discord bot
if [ -d "services/discord-bot" ] && [ -f "services/discord-bot/Gemfile" ]; then
    echo "📦 Installing Discord bot dependencies..."
    cd services/discord-bot
    bundle install
    cd ../..
fi

# Install Ruby dependencies for DSL compiler
if [ -d "services/dsl-compiler" ] && [ -f "services/dsl-compiler/Gemfile" ]; then
    echo "📦 Installing DSL compiler dependencies..."
    cd services/dsl-compiler
    bundle install
    cd ../..
fi

# Install development tools
echo "🔧 Installing development tools..."
pip install pytest pytest-cov ruff black isort

# Create .env from example if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
fi

# Create .env for backend if it doesn't exist
if [ ! -f "backend/.env" ] && [ -f "backend/.env.example" ]; then
    echo "📝 Creating backend/.env from backend/.env.example..."
    cp backend/.env.example backend/.env
fi

echo "✅ AURA development environment setup complete!"
echo ""
echo "📋 Quick Start:"
echo "  1. Backend:     python -m uvicorn ame_backend.main:app --reload"
echo "  2. Frontend:    cd frontend && npm run dev"
echo "  3. Discord Bot: cd services/discord-bot && ruby bot.rb"
echo "  4. HF Space:    cd hf-space && python app.py"
echo "  5. All:         docker-compose up --build"
echo ""
echo "🧪 Tests:"
echo "  Python: pytest services/gesture-control/tests services/voice-commands/tests tests/integration tests/unit"
echo "  Ruby:   rspec services/discord-bot/spec services/dsl-compiler/spec"
