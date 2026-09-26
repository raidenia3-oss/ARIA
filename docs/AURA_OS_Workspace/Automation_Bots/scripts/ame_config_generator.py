#!/usr/bin/env python3
"""
ame_config_generator.py — Genera ame_config.json para el celular (AME/Android)
Lee aura_urls.json (generado por setup_cloudflare.py) y genera el config
que AME debe copiar a /sdcard/ame_config.json.

Uso:
  python scripts/ame_config_generator.py
  # → Genera aura_urls/ame_config.json listo para copiar al celular
"""

import json
import os
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
URLS_FILE = ROOT_DIR / "aura_urls.json"
OUTPUT_DIR = ROOT_DIR / "aura_urls"
OUTPUT_FILE = OUTPUT_DIR / "ame_config.json"
LOCAL_FALLBACK = "ws://192.168.1.100:8765"

def generate_config():
    """Genera ame_config.json a partir de aura_urls.json"""
    
    # Leer URLs del túnel
    urls_data = {}
    if URLS_FILE.exists():
        with open(URLS_FILE) as f:
            urls_data = json.load(f)
    else:
        print("⚠️  aura_urls.json no encontrado.")
        print("   Ejecuta primero: python scripts/setup_cloudflare.py")
        print("   Usando fallback local...")
    
    urls = urls_data.get("urls", {})
    mode = urls_data.get("mode", "unknown")
    fallback = urls_data.get("fallback", {})
    
    # Configuración para AME (el que se copia a /sdcard/)
    ame_config = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "network": {
            "eventbus_url": urls.get("eventbus", fallback.get("eventbus", LOCAL_FALLBACK)),
            "godot_url": urls.get("godot", fallback.get("godot", "")),
            "dashboard_url": urls.get("dashboard", fallback.get("dashboard", "")),
            "timeout": 30,
            "retry_interval": 5
        },
        "sync": {
            "interval": 30,
            "telemetry_enabled": True,
            "heartbeat_interval": 10
        },
        "tunnel": {
            "type": mode,
            "note": "URLs generadas por setup_cloudflare.py" if mode != "local" else "Fallback a WiFi local"
        },
        "node": {
            "node_id": f"AME_ANDROID_{datetime.now().strftime('%Y%m%d')}",
            "role": "mobile",
            "capabilities": ["telemetry", "osint", "sensors"]
        }
    }
    
    # Guardar
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(ame_config, f, indent=2)
    
    print(f"✅ ame_config.json generado en: {OUTPUT_FILE}")
    print()
    print("📱 Para conectar AME (Android/Termux):")
    print(f"   1. Copia este archivo a /sdcard/ame_config.json en el celular:")
    print(f"      cp {OUTPUT_FILE} /sdcard/ame_config.json")
    print()
    print(f"   2. O vía adb:")
    print(f"      adb push {OUTPUT_FILE} /sdcard/ame_config.json")
    print()
    
    # Mostrar URLs
    if mode != "local":
        print("🌐 URLs del túnel:")
        for name, url in urls.items():
            print(f"   {name:12s}: {url}")
    else:
        print(f"📡 Fallback WiFi local: {LOCAL_FALLBACK}")
    
    return ame_config


if __name__ == "__main__":
    print("=" * 55)
    print("  AURA AME — Generador de Configuración")
    print("=" * 55)
    generate_config()