#!/usr/bin/env python3
"""
AURA Perimetral Check — Diagnóstico de conectividad
Genera audit.log con el estado de los proveedores de IA.
"""
import sys
import json
import os

# Añadir AURA_Core al path
AURA_CORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AURA_Core')
if AURA_CORE_DIR not in sys.path:
    sys.path.insert(0, AURA_CORE_DIR)

try:
    from ai_router import AuraCognitiveRouter
    router = AuraCognitiveRouter()
    providers = router.list_available_providers()

    # Escribir audit.log
    with open('audit.log', 'w', encoding='utf-8') as f:
        f.write("🔑 AURA Perimetral Check — Diagnóstico de Conectividad\n")
        f.write("="*60 + "\n")
        f.write(f"Timestamp: {__import__('time').strftime('%Y-%m-%dT%H:%M:%S')}\n")
        f.write(f"Total providers: {len(providers)}\n\n")
        for p in providers:
            f.write(f"  ✅ {p.get('name', 'unknown')}\n")
            if p.get('model'):
                f.write(f"     Model: {p['model']}\n")
            if p.get('type'):
                f.write(f"     Type: {p['type']}\n")
        f.write("\n📊 Status: OK\n")

    print("✅ audit.log generado con éxito")

except Exception as e:
    with open('audit.log', 'w', encoding='utf-8') as f:
        f.write(f"❌ Error: {str(e)}\n")
    print(f"❌ Error: {e}")