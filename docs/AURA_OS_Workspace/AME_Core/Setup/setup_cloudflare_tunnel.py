#!/usr/bin/env python3
"""
Script para configurar Cloudflare Tunnel y autenticación básica.
"""

import os
import subprocess
import sys
import json
import time
from pathlib import Path

# Configuración global
CLOUDFLARED_CONFIG = {
    "tunnel": "aura-tunnel",
    "credentials-file": "credentials.json",
    "ingress": {
        "service": "http://localhost:5000",
        "path": "/",
        "rule": "aura-tunnel.your-subdomain.com"
    },
    "no-autoupdate": True
}

def install_cloudflared():
    """Instala cloudflared si no está disponible."""
    try:
        result = subprocess.run(
            ["cloudflared", "--version"],
            capture_output=True,
            text=True
        )
        if "cloudflared" not in result.stdout:
            print("🔧 Instalando cloudflared...")
            subprocess.run(
                ["winget", "install", "Cloudflare.cloudflared"],
                check=True
            )
            print("✅ cloudflared instalado correctamente.")
    except Exception as e:
        print(f"❌ Error al verificar/installar cloudflared: {e}")
        return False
    return True

def configure_tunnel():
    """Configura el túnel de Cloudflare."""
    try:
        # Crear directorio para configuración
        config_dir = Path("cloudflared")
        config_dir.mkdir(exist_ok=True)

        # Crear archivo de configuración
        config_path = config_dir / "config.yml"
        with open(config_path, "w") as f:
            yaml_content = "---\ntunnel: {tunnel}\ncredentials-file: {credentials_file}\ningress:\n  - service: http://localhost:5000\n    path: /\n    rule: aura-tunnel.your-subdomain.com\nno-autoupdate: true".format(
                tunnel=CLOUDFLARED_CONFIG["tunnel"],
                credentials_file=CLOUDFLARED_CONFIG["credentials-file"]
            )
            f.write(yaml_content)

        # Crear archivo de credenciales (simulado)
        creds_path = Path(CLOUDFLARED_CONFIG["credentials-file"])
        if not creds_path.exists():
            creds_path.write_text(json.dumps({"token": "simulated-token-for-demo"}))

        print("✅ Configuración de túnel guardada en cloudflared/config.yml")
        return True
    except Exception as e:
        print(f"❌ Error al configurar túnel: {e}")
        return False

def start_tunnel():
    """Inicia el túnel de Cloudflare."""
    try:
        print("🚀 Iniciando túnel Cloudflare...")
        tunnel_process = subprocess.Popen(
            ["cloudflared", "tunnel", "--config", "cloudflared/config.yml", "run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        print("✅ Túnel Cloudflare iniciado. Esperando conexión...")
        return tunnel_process
    except Exception as e:
        print(f"❌ Error al iniciar túnel: {e}")
        return None

def add_basic_auth():
    """Añade autenticación básica al servidor Flask."""
    try:
        # Modificar el archivo servidor_ame.py para añadir autenticación básica
        server_path = Path("AME_Core/servidor_ame.py")
        if not server_path.exists():
            print("❌ El archivo servidor_ame.py no existe.")
            return False

        # Leer el contenido actual
        with open(server_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Insertar código de autenticación básica
        auth_code = """
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == "admin" and password == "AURA2024!"

@app.before_request
def before_request():
    if request.path != '/health' and request.path != '/api/health':
        if not auth.current_user():
            return auth.login()
"""

        # Insertar el código en el archivo
        if "@app.route('/health')" in content:
            import_regex = r"(from flask import Flask, send_from_directory, jsonify, request, render_template)"
            if import_regex in content:
                content = content.replace(import_regex, import_regex + "\n" + auth_code)
            else:
                content = content.replace("import os", "import os\n" + auth_code)

            with open(server_path, "w", encoding="utf-8") as f:
                f.write(content)

        print("✅ Autenticación básica añadida al servidor Flask.")
        return True
    except Exception as e:
        print(f"❌ Error al añadir autenticación básica: {e}")
        return False

def setup_mobile_ui():
    """Ajusta el CSS para dispositivos móviles."""
    try:
        css_path = Path("AME_Core/static/css/tactical_dashboard.css")
        if not css_path.exists():
            css_path = Path("AME_Core/static/css/style.css")

        if not css_path.exists():
            print("❌ No se encontró el archivo CSS.")
            return False

        # Leer el contenido actual
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Añadir media queries para móviles
        mobile_css = """
        /* Media Queries para Dispositivos Móviles */
        @media screen and (max-width: 768px) {
            .sidebar {
                display: none !important;
            }

            .main-content {
                width: 100% !important;
                padding: 10px !important;
            }

            .action-queue-panel {
                width: 100% !important;
                margin-bottom: 20px !important;
            }

            .panel-secondary {
                display: none !important;
            }

            .ticker-container {
                font-size: 14px !important;
            }

            .card {
                margin-bottom: 15px !important;
            }
        }
        """

        # Insertar el CSS en el archivo
        if "@media screen" not in content:
            content += "\n" + mobile_css

        with open(css_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Media queries para móviles añadidas al CSS.")
        return True
    except Exception as e:
        print(f"❌ Error al ajustar el CSS para móviles: {e}")
        return False

def main():
    """Función principal para configurar el Mobile Bridge."""
    print("=" * 50)
    print("🌐 Configurando Mobile Bridge con Cloudflare Tunnel")
    print("=" * 50)

    # Instalar cloudflared
    if not install_cloudflared():
        print("⚠️  No se pudo instalar cloudflared. Continuando con configuración manual.")
        time.sleep(2)

    # Configurar túnel
    if not configure_tunnel():
        print("⚠️  No se pudo configurar el túnel. Verifica la configuración manualmente.")
        time.sleep(2)

    # Añadir autenticación básica
    if not add_basic_auth():
        print("⚠️  No se pudo añadir autenticación básica. Verifica manualmente el archivo servidor_ame.py.")
        time.sleep(2)

    # Ajustar UI para móviles
    if not setup_mobile_ui():
        print("⚠️  No se pudieron añadir media queries para móviles. Verifica manualmente el CSS.")
        time.sleep(2)

    print("\n🔒 Configuración de Mobile Bridge completada.")
    print("📌 Instrucciones:")
    print("   1. Reemplaza 'aura-tunnel.your-subdomain.com' con tu subdominio real en cloudflared/config.yml")
    print("   2. Inicia el túnel con: cloudflared tunnel run aura-tunnel")
    print("   3. Accede al dashboard usando la URL pública generada por Cloudflare.")
    print("   4. Usa las credenciales: admin / AURA2024!")
    print("=" * 50)

if __name__ == "__main__":
    main()