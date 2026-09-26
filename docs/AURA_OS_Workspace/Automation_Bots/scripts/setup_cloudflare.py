#!/usr/bin/env python3
"""
setup_cloudflare.py — Instalación y configuración automática de Cloudflare Tunnel
Detecta Windows/Linux, instala cloudflared, configura túnel "aura-core" y genera URLs.
Soporta: dominio propio en Cloudflare OU trycloudflare.com (gratuito sin cuenta).
"""

import os
import sys
import platform
import subprocess
import json
import shutil
from pathlib import Path

# ── Constantes ──
CONFIG_DIR = Path.home() / ".cloudflared"
TUNNEL_NAME = "aura-core"
AURA_CONFIG = Path(__file__).resolve().parent.parent / "AURA_Core" / "config.json"
URLS_FILE = Path(__file__).resolve().parent.parent / "aura_urls.json"

# Servicios de AURA que se exponen por el túnel
SERVICES = {
    "eventbus": {"port": 8765, "proto": "ws",  "desc": "EventBus WebSocket"},
    "godot":    {"port": 9090, "proto": "ws",  "desc": "Godot Bridge WebSocket"},
    "dashboard":{"port": 5000, "proto": "http", "desc": "Dashboard HTTP"},
}

def get_os():
    s = platform.system().lower()
    return "windows" if s == "windows" else "linux"

def install_cloudflared():
    os_name = get_os()
    print(f"\n🔧 Detectado: {platform.system()} ({platform.machine()})")
    
    # Verificar si ya está instalado
    try:
        result = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ cloudflared ya instalado: {result.stdout.strip().split(chr(10))[0]}")
            return True
    except FileNotFoundError:
        pass

    print("📥 Instalando cloudflared...")
    
    if os_name == "windows":
        try:
            subprocess.run(["winget", "install", "-e", "--id", "Cloudflare.cloudflared"], check=True)
            print("✅ cloudflared instalado vía winget")
            return True
        except Exception:
            print("⚠️  winget no disponible. Descargando binario...")
            # Descarga manual en Windows
            import urllib.request
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
            dest = Path(os.environ.get("USERPROFILE", ".")) / "cloudflared.exe"
            print(f"📥 Descargando de {url}...")
            try:
                urllib.request.urlretrieve(url, str(dest))
                print(f"✅ Descargado en {dest}")
                print("   Añade este directorio al PATH o ejecuta con la ruta completa.")
                return True
            except Exception as e:
                print(f"❌ Error descargando: {e}")
                print("   Descarga manualmente desde: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/")
                return False
    
    else:  # Linux
        try:
            subprocess.run(
                ["wget", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb",
                 "-O", "/tmp/cloudflared.deb"],
                check=True, capture_output=True
            )
            subprocess.run(["sudo", "dpkg", "-i", "/tmp/cloudflared.deb"], check=True, capture_output=True)
            print("✅ cloudflared instalado vía .deb")
            return True
        except Exception:
            print("⚠️  No se pudo instalar vía .deb, intentando con npm...")
            try:
                subprocess.run(["npm", "install", "-g", "cloudflared"], check=True)
                print("✅ cloudflared instalado vía npm")
                return True
            except Exception as e:
                print(f"❌ Error instalando: {e}")
                print("   Instala manualmente: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/")
                return False

def choose_mode():
    """Pregunta al usuario si tiene dominio en Cloudflare o quiere usar trycloudflare.com"""
    print("\n" + "="*50)
    print("  🌐 MODO DE TÚNEL CLOUDFLARE")
    print("="*50)
    print()
    print("  ¿Cómo quieres exponer AURA al exterior?")
    print()
    print("  [1] 🆓 trycloudflare.com (GRATIS, sin cuenta, URL temporal)")
    print("      - URL aleatoria tipo https://random-name.trycloudflare.com")
    print("      - Ideal para pruebas rápidas")
    print()
    print("  [2] 🌍 Dominio propio en Cloudflare (requiere cuenta)")
    print("      - URL permanente tipo https://aura.mi-dominio.com")
    print("      - Requiere tener dominio registrado en Cloudflare")
    print()
    
    while True:
        choice = input("  Selecciona [1 o 2]: ").strip()
        if choice in ("1", "2"):
            return choice
        print("  Por favor, introduce 1 o 2")

def setup_trycloudflare():
    """Configura el túnel usando trycloudflare.com (sin cuenta necesaria)"""
    print("\n🆓 Configurando modo trycloudflare.com...")
    print("   Esto creará URLs temporales gratuitas.")
    print()
    
    # Crear config mínimo
    config_path = CONFIG_DIR / "config-aura.yml"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    config_content = f"""---
# AURA Core - Cloudflare Tunnel (trycloudflare.com)
# Generado por setup_cloudflare.py
# Las URLs se asignan dinámicamente cuando cloudflared se conecta

ingress:
  - service: http://localhost:{SERVICES['eventbus']['port']}
  - service: http://localhost:{SERVICES['dashboard']['port']}
    path: /
  - service: http_status:404
"""
    
    config_path.write_text(config_content)
    print(f"  ✅ Configuración guardada en {config_path}")
    
    return {
        "mode": "trycloudflare",
        "config_file": str(config_path),
        "note": "Las URLs temporales aparecen en la consola de cloudflared. Ejecuta: cloudflared tunnel --url http://localhost:8765 --config <config_path>"
    }

def setup_own_domain():
    """Configura el túnel con dominio propio en Cloudflare"""
    print("\n🌍 Configurando dominio propio en Cloudflare...")
    
    # Paso 1: Login con Cloudflare
    print("\n📋 Paso 1: Autenticar con Cloudflare")
    print("   Se abrirá tu navegador para autenticar.")
    print("   Selecciona el dominio que quieres usar.")
    input("   Presiona ENTER cuando estés listo...")
    
    try:
        subprocess.run(["cloudflared", "tunnel", "login"], check=True)
    except FileNotFoundError:
        print("❌ cloudflared no encontrado. Instálalo primero.")
        return None
    except Exception as e:
        print(f"⚠️  Error en login (puede ser normal si ya estás autenticado): {e}")
    
    # Paso 2: Crear túnel
    print("\n📋 Paso 2: Creando túnel 'aura-core'...")
    result = subprocess.run(
        ["cloudflared", "tunnel", "create", TUNNEL_NAME],
        capture_output=True, text=True
    )
    tunnel_id = None
    if result.returncode == 0:
        # Extraer ID del output
        for line in result.stdout.strip().split('\n'):
            if len(line) > 30:
                tunnel_id = line.strip()
                break
        print(f"✅ Túnel creado: {tunnel_id}")
    else:
        print(f"⚠️  Error: {result.stderr}")
        print("   El túnel puede que ya exista. Continuando...")
    
    # Paso 3: Pedir dominio
    print("\n📋 Paso 3: Configurar dominio")
    domain = input("   Introduce tu dominio (ej: aura.midominio.com): ").strip()
    
    if not domain:
        print("❌ Dominio requerido.")
        return None
    
    # Paso 4: Crear config.yml
    config_path = CONFIG_DIR / "config-aura.yml"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Buscar credentials file
    creds_file = ""
    if tunnel_id:
        for f in CONFIG_DIR.glob("*.json"):
            if tunnel_id in f.name:
                creds_file = str(f)
                break
    
    config_content = f"""---
# AURA Core - Cloudflare Tunnel
# Tunnel ID: {tunnel_id or 'TUNNEL_ID'}
# Dominio: {domain}

tunnel: {tunnel_id or 'TUNNEL_ID'}
credentials-file: {creds_file or '~/.cloudflared/TUNNEL_ID.json'}

ingress:
  - hostname: aura-eventbus.{domain}
    service: http://localhost:{SERVICES['eventbus']['port']}
  - hostname: aura-godot.{domain}
    service: http://localhost:{SERVICES['godot']['port']}
  - service: http://localhost:{SERVICES['dashboard']['port']}
    path: /
  - service: http_status:404
"""
    
    config_path.write_text(config_content)
    print(f"  ✅ Configuración guardada en {config_path}")
    
    # Paso 5: Configurar DNS route
    if tunnel_id:
        print("\n📋 Paso 5: Configurando DNS route...")
        for svc_name, svc_info in SERVICES.items():
            hostname = f"aura-{svc_name}.{domain}"
            try:
                result = subprocess.run(
                    ["cloudflared", "tunnel", "route", "dns", tunnel_id, hostname],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    print(f"  ✅ DNS configurado: {hostname}")
                else:
                    print(f"  ⚠️  {hostname}: {result.stderr.strip()[:80]}")
            except Exception as e:
                print(f"  ⚠️  {hostname}: {e}")
    
    return {
        "mode": "own_domain",
        "tunnel_id": tunnel_id,
        "domain": domain,
        "config_file": str(config_path),
        "urls": {
            "eventbus": f"wss://aura-eventbus.{domain}",
            "godot": f"wss://aura-godot.{domain}",
            "dashboard": f"https://{domain}"
        }
    }

def save_urls(result):
    """Guarda las URLs del túnel en aura_urls.json para que AME las lea"""
    urls_data = {
        "generated_at": datetime.now().isoformat() if 'datetime' in dir() else "now",
        "mode": result.get("mode", "unknown"),
        "tunnel_id": result.get("tunnel_id", ""),
        "urls": result.get("urls", {}),
        "fallback": {
            "eventbus": "ws://192.168.1.100:8765",
            "dashboard": "http://192.168.1.100:5000"
        },
        "ame_config_note": "Copia este archivo a /sdcard/ame_config.json en el celular"
    }
    
    URLS_FILE.write_text(json.dumps(urls_data, indent=2))
    print(f"\n📁 URLs guardadas en: {URLS_FILE}")

def print_summary(result):
    """Imprime el resumen final con URLs y próximos pasos"""
    print("\n" + "="*60)
    print("  ✅ CONFIGURACIÓN DE TÚNEL CLOUDFLARE COMPLETADA")
    print("="*60)
    
    if result["mode"] == "trycloudflare":
        print("\n  📝 Modo: trycloudflare.com (gratuito)")
        print()
        print("  Para iniciar el túnel ejecuta:")
        print("    cloudflared tunnel --url http://localhost:8765")
        print()
        print("  Las URLs temporales aparecerán en la consola.")
        print("  Ejemplo: https://random-name-abc.trycloudflare.com")
        print()
        print("  ⚠️  Las URLs cambian cada vez que reinicias cloudflared.")
    else:
        print(f"\n  📝 Modo: Dominio propio ({result.get('domain', 'N/A')})")
        urls = result.get("urls", {})
        print()
        print("  URLs para AME:")
        for name, url in urls.items():
            desc = SERVICES.get(name, {}).get("desc", "")
            print(f"    {desc:25s} → {url}")
        
        print()
        print("  Para iniciar:")
        print(f"    cloudflared tunnel --config {result.get('config_file', '~/.cloudflared/config-aura.yml')}")
    
    print()
    print("  📱 Para conectar AME (Android/Termux):")
    print("    1. Copia aura_urls.json a /sdcard/ame_config.json")
    print("    2. Ejecuta python join_swarm.py --server <url_del_eventbus>")
    print()
    print("="*60)

# ─── PUNTO DE ENTRADA ───
if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║  AURA Core — Configuración Cloudflare   ║")
    print("║  Tunnel Setup para acceso remoto         ║")
    print("╚══════════════════════════════════════════╝")
    
    # Paso 1: Instalar cloudflared
    if not install_cloudflared():
        print("\n❌ No se pudo instalar cloudflared. Instálalo manualmente.")
        print("   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/")
        sys.exit(1)
    
    # Paso 2: Elegir modo
    mode = choose_mode()
    
    # Paso 3: Configurar según el modo
    if mode == "1":
        result = setup_trycloudflare()
    else:
        result = setup_own_domain()
    
    if result:
        # Paso 4: Guardar URLs
        save_urls(result)
        
        # Paso 5: Resumen
        print_summary(result)
    else:
        print("\n❌ Configuración cancelada o fallida.")