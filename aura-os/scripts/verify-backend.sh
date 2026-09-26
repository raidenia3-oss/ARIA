#!/bin/sh
# AURA Backend Verification - Ejecutar en Alpine LIVE
set -e

echo "╔════════════════════════════════════════════╗"
echo "║    AURA Backend Verification              ║"
echo "╚════════════════════════════════════════════╝"
echo ""

echo "Verificando Alpine..."
if [ -f /etc/alpine-release ]; then
  echo "✓ Alpine corriendo"
else
  echo "✗ Alpine no detectado"
  exit 1
fi

echo "Verificando AURA backend..."
if [ -d /opt/aura/backend ]; then
  echo "✓ AURA backend encontrado"
else
  echo "✗ AURA backend no encontrado"
  exit 1
fi

echo "Verificando puerto 8000..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
  echo "✓ Backend responde en :8000"
  curl -s http://localhost:8000/health | jq .
else
  echo "⚠ Backend no responde aún (esperando 5 seg)..."
  sleep 5
  curl -s http://localhost:8000/health | jq .
fi

echo ""
echo "✓ AURA Backend Operativo"
echo ""
