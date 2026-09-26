"""
AURA Install Manager — install_manager.py
Agente de mantenimiento para instalar paquetes en Termux vía SSH.
- Verifica peso del paquete antes de instalar (usa 'pkg show')
- Si excede 50MB, pide confirmación antes de proceder
- Prioriza versiones 'light' o 'static' de herramientas OSINT
- Reporta estado al system_health.log
"""
import os
import sys
import json
import subprocess
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
HEALTH_LOG = os.path.join(BASE_DIR, "system_health.log")
MAX_INSTALL_MB = 50  # límite por defecto


def log_health(component, status, detail=""):
    """Escribe en system_health.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {component}: {status}"
    if detail:
        entry += f" — {detail}"
    with open(HEALTH_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(entry)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_ssh_target(cfg):
    mobile_ip = cfg.get("mobile_ip", "192.168.1.0")
    ssh_user = cfg.get("ssh_user", "u0_a316")
    ssh_port = cfg.get("ssh_port", 8022)
    ssh_key = cfg.get("ssh_key", os.path.expanduser("~/.ssh/id_rsa"))
    return mobile_ip, ssh_user, ssh_port, ssh_key


def ssh_run(host, user, port, key, command):
    """Ejecuta un comando en Termux vía SSH y devuelve stdout."""
    cmd = [
        "ssh",
        "-p", str(port),
        "-i", key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        f"{user}@{host}",
        command
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "SSH timeout", 1
    except FileNotFoundError:
        return "", "ssh not found", 1
    except Exception as e:
        return "", str(e), 1


def check_package_size(host, user, port, key, package):
    """
    Verifica el tamaño de un paquete en Termux usando 'pkg show'.
    Retorna (size_mb, version, description) o None si no se pudo determinar.
    """
    stdout, stderr, rc = ssh_run(host, user, port, key, f"pkg show {package} 2>/dev/null")

    if rc != 0 or not stdout:
        # Fallback: intentar con apt-cache
        stdout, stderr, rc = ssh_run(host, user, port, key, f"apt-cache show {package} 2>/dev/null")

    if rc != 0 or not stdout:
        return None

    size_mb = 0
    version = "unknown"
    description = ""

    for line in stdout.split("\n"):
        line_lower = line.lower()
        if line_lower.startswith("version:"):
            version = line.split(":", 1)[1].strip()
        elif "size" in line_lower:
            # pkg show: "Installed-Size: 1234 kB"
            # apt-cache: "Size: 123456"
            try:
                parts = line.split(":", 1)[1].strip()
                if "kb" in parts.lower() or "mb" in parts.lower():
                    # Parse human-readable
                    val = parts.lower().replace("kb", "").replace("mb", "").strip()
                    size_mb = float(val) / 1024 if "kb" in line_lower.lower() else float(val)
                else:
                    # Bytes
                    size_bytes = int(''.join(c for c in parts if c.isdigit()))
                    size_mb = size_bytes / (1024 * 1024)
            except (ValueError, IndexError):
                pass
        elif line_lower.startswith("description:"):
            description = line.split(":", 1)[1].strip()[:120]

    return {
        "package": package,
        "version": version,
        "size_mb": round(size_mb, 2),
        "description": description
    }


def install_package(host, user, port, key, package, force=False):
    """Instala un paquete en Termux vía SSH."""
    cmd = f"pkg install -y {package}"
    print(f"📦 Instalando {package} en Termux...")
    stdout, stderr, rc = ssh_run(host, user, port, key, cmd)

    if rc == 0:
        log_health("INSTALL_MANAGER", "OK", f"Paquete {package} instalado")
        print(f"✅ {package} instalado correctamente")
        return {"status": "ok", "package": package, "output": stdout[:300]}
    else:
        log_health("INSTALL_MANAGER", "ERROR", f"Fallo instalando {package}: {stderr[:200]}")
        print(f"❌ Error instalando {package}: {stderr[:200]}")
        return {"status": "error", "package": package, "error": stderr[:300]}


def find_light_version(package):
    """Sugiere versiones ligeras de herramientas OSINT conocidas."""
    LIGHT_MAP = {
        "phoneinfoga": "phoneinfoga",  # es Go single binary
        "mrholmes": "mrholmes",
        "nmap": "nmap",
        "hydra": "hydra",
        "sqlmap": "sqlmap",
        "python": "python",  # viene con Termux
        "nodejs": "nodejs-lts",  # versión LTS más ligera
    }
    return LIGHT_MAP.get(package.lower(), package)


def interactive_check(pkg_info):
    """Pregunta al usuario si quiere instalar un paquete pesado."""
    print(f"\n📊 Paquete: {pkg_info['package']}")
    print(f"   Versión: {pkg_info['version']}")
    print(f"   Tamaño:  {pkg_info['size_mb']} MB")
    print(f"   Desc:    {pkg_info['description']}")

    if pkg_info['size_mb'] > MAX_INSTALL_MB:
        print(f"\n⚠️  Este paquete excede el límite de {MAX_INSTALL_MB} MB")
        response = input("¿Instalar de todas formas? (s/N): ").strip().lower()
        return response == "s" or response == "si"
    return True


# ────────────── CLI ──────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AURA Install Manager — Termux")
    parser.add_argument("action", choices=["check", "install", "list-packages"],
                        help="Acción a realizar")
    parser.add_argument("--package", "-p", help="Nombre del paquete")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Saltar verificación de tamaño")
    parser.add_argument("--limit", type=int, default=MAX_INSTALL_MB,
                        help=f"Límite de tamaño en MB (defecto: {MAX_INSTALL_MB})")
    args = parser.parse_args()

    cfg = load_config()
    host, user, port, key = get_ssh_target(cfg)

    if args.action == "check":
        if not args.package:
            print("❌ Especifica --package")
            sys.exit(1)

        light_pkg = find_light_version(args.package)
        print(f"🔍 Verificando {light_pkg} en Termux...")
        pkg_info = check_package_size(host, user, port, key, light_pkg)

        if pkg_info:
            print(f"\n📦 {pkg_info['package']} v{pkg_info['version']}")
            print(f"   Tamaño instalado: {pkg_info['size_mb']} MB")
            print(f"   Descripción: {pkg_info['description']}")
            log_health("INSTALL_MANAGER", "OK", f"Check {light_pkg}: {pkg_info['size_mb']}MB")
        else:
            print(f"❌ No se pudo obtener información de {light_pkg}")
            log_health("INSTALL_MANAGER", "ERROR", f"No info para {light_pkg}")

    elif args.action == "install":
        if not args.package:
            print("❌ Especifica --package")
            sys.exit(1)

        light_pkg = find_light_version(args.package)
        pkg_info = check_package_size(host, user, port, key, light_pkg)

        if pkg_info:
            proceed = args.force or interactive_check(pkg_info)
            if proceed:
                install_package(host, user, port, key, light_pkg, args.force)
            else:
                print("⏭️  Instalación cancelada por el usuario")
                log_health("INSTALL_MANAGER", "OK", f"Cancelado por usuario: {light_pkg}")
        else:
            print(f"⚠️  No se pudo verificar tamaño. Instalando de todas formas...")
            install_package(host, user, port, key, light_pkg, force=True)

    elif args.action == "list-packages":
        print("📋 Listando paquetes instalados en Termux...")
        stdout, stderr, rc = ssh_run(host, user, port, key, "pkg list-installed 2>/dev/null | head -50")
        if rc == 0:
            print(stdout)
        else:
            print(f"Error: {stderr[:200]}")