#!/bin/bash
# Instala las dependencias de la Fase 58 (backend de Cline).
# Requiere Python 3.10+ y, opcionalmente, un entorno virtual.

set -e

echo "🔧 Installing Phase 58 dependencies..."

python -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate || source venv/Scripts/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Phase 58 dependencies installed"
echo ""
echo "Next steps:"
echo "1. source venv/bin/activate   # Windows: venv\\Scripts\\activate"
echo "2. cp frontend/.env.example frontend/.env.local  (editar credenciales)"
echo "3. Sigue setup-phase-58.md"
