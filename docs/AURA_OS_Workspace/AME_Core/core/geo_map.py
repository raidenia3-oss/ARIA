#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════
# AURA GLOBAL COMMAND MAP — Mapa Geopolítico Modular
# Mapea la infraestructura del ecosistema AURA/AME:
#   - Nodo Central (PC local)
#   - Nodo de Conciencia (Hugging Face)
#   - Indicadores de Objetivos (servidores de interés)
# Genera geo_coordinates.json para la interfaz Android.
# ══════════════════════════════════════════════════════════════

import json
import socket
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "geo_coordinates.json"

HF_SERVER = "https://raiden456-slut.hf.space"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_public_ip():
    try:
        resp = urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5)
        return json.loads(resp.read().decode())["ip"]
    except Exception:
        return "unknown"


def geolocate_ip(ip):
    """Obtiene geolocalización aproximada de una IP pública."""
    try:
        resp = urllib.request.urlopen(f"http://ip-api.com/json/{ip}", timeout=5)
        data = json.loads(resp.read().decode())
        return {
            "lat": data.get("lat", 0),
            "lon": data.get("lon", 0),
            "city": data.get("city", "Unknown"),
            "country": data.get("country", "Unknown"),
            "org": data.get("org", "Unknown"),
        }
    except Exception:
        return {"lat": 0, "lon": 0, "city": "Unknown", "country": "Unknown", "org": "Unknown"}


def build_ecosystem_nodes():
    """Construye los nodos del ecosistema AURA."""
    local_ip = get_local_ip()
    public_ip = get_public_ip()
    geo = geolocate_ip(public_ip)

    nodes = [
        {
            "id": "nodo_central",
            "name": "🖥️ Nodo Central — PC Local",
            "type": "central",
            "ip_local": local_ip,
            "ip_public": public_ip,
            "lat": geo["lat"],
            "lon": geo["lon"],
            "city": geo["city"],
            "country": geo["country"],
            "org": geo["org"],
            "status": "ACTIVE",
            "color": "#00FF41",
            "description": "Estación de comando principal del ecosistema AURA",
        },
        {
            "id": "nodo_conciencia",
            "name": "☁️ Nodo de Conciencia — Hugging Face",
            "type": "cloud",
            "url": HF_SERVER,
            "lat": 48.8566,
            "lon": 2.3522,
            "city": "Paris",
            "country": "France",
            "org": "Hugging Face (OVH Hosting)",
            "status": "ONLINE",
            "color": "#FFD700",
            "description": "Servidor permanente con modelo Qwen para análisis táctico",
        },
        {
            "id": "nodo_emulador",
            "name": "📱 Nodo Emulador — Android AVD",
            "type": "emulator",
            "ip": "10.0.2.2",
            "lat": geo["lat"],
            "lon": geo["lon"],
            "city": geo["city"],
            "country": geo["country"],
            "status": "ACTIVE",
            "color": "#00BFFF",
            "description": "Emulador Android conectado vía ADB",
        },
    ]

    # Indicadores de objetivos — servidores de interés
    targets = [
        {
            "id": "target_huggingface_api",
            "name": "🤗 Hugging Face Inference API",
            "type": "target",
            "url": "https://api-inference.huggingface.co",
            "lat": 48.8566,
            "lon": 2.3522,
            "city": "Paris",
            "country": "France",
            "status": "MONITORING",
            "color": "#FF6B6B",
        },
        {
            "id": "target_ollama_registry",
            "name": "🦙 Ollama Model Registry",
            "type": "target",
            "url": "https://registry.ollama.ai",
            "lat": 37.7749,
            "lon": -122.4194,
            "city": "San Francisco",
            "country": "USA",
            "status": "STANDBY",
            "color": "#FF6B6B",
        },
        {
            "id": "target_github",
            "name": "🐙 GitHub — AURA Repository",
            "type": "target",
            "url": "https://github.com/raidenia3-oss/AURA-server.01",
            "lat": 37.7749,
            "lon": -122.4194,
            "city": "San Francisco",
            "country": "USA",
            "status": "SYNCED",
            "color": "#FF6B6B",
        },
        {
            "id": "target_cloudflare",
            "name": "🛡️ Cloudflare Tunnel",
            "type": "target",
            "url": "https://cloudflare.com",
            "lat": 37.3861,
            "lon": -122.0839,
            "city": "San Jose",
            "country": "USA",
            "status": "STANDBY",
            "color": "#FF6B6B",
        },
    ]

    return nodes, targets


def generate_geo_data():
    """Genera el archivo geo_coordinates.json."""
    nodes, targets = build_ecosystem_nodes()

    data = {
        "timestamp": datetime.now().isoformat(),
        "ecosystem": "AURA/AME",
        "nodes": nodes,
        "targets": targets,
        "summary": {
            "total_nodes": len(nodes),
            "total_targets": len(targets),
            "active_nodes": sum(1 for n in nodes if n["status"] == "ACTIVE"),
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data


if __name__ == "__main__":
    data = generate_geo_data()
    print(f"🌍 AURA Global Command Map — Coordenadas generadas")
    print(f"📁 Archivo: {OUTPUT_FILE}")
    print(
        f"📍 Nodos: {data['summary']['total_nodes']} | Objetivos: {data['summary']['total_targets']}"
    )
    for n in data["nodes"]:
        print(f"   🔹 {n['name']} → {n.get('city', 'N/A')}, {n.get('country', 'N/A')}")
