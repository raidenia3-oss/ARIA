#!/bin/bash
# scripts/autonomous-setup.sh

echo "AURA Autonomous Setup Agent (macOS/Linux)"
echo ""

if ! command -v python &> /dev/null; then
    echo "Python not found. Install Python 3.10+"
    exit 1
fi

# Run as module to avoid ModuleNotFoundError
python -m ame_backend.src.automation.config_agent

if [ $? -eq 0 ]; then
    echo ""
    echo "Setup successful!"
    echo ""
    echo "Opening browser..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:8000/health"
    else
        xdg-open "http://localhost:8000/health"
    fi
else
    echo ""
    echo "Setup failed. Check errors above."
    exit 1
fi
