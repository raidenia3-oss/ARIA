"""
AURA Termux Sync — sync_termux.py
Conecta con el dispositivo móvil (Termux/AME) mediante SCP o rsync
para descargar logs, archivos y resultados OSINT generados en el celular.

Uso:
  python sync_termux.py                     # sync completo
  python sync_termux.py --mode rsync        # usar rsync (más rápido)
  python sync_termux.py --mode scp          # usar SCP (por defecto)

Configuración:
  - La IP del móvil se lee de AURA_Core/config.json (mobile_ip)
  - Puerto SSH de Termux: 8022 (por defecto)
  - Usuario Termux: u0_a316 (o el configurado)
"""
import os
import sys
import json
import subprocess
import argparse
from datetime import datetime

# ── Rutas ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SYNC_DEST = os.path.join(PROJECT_DIR, "AME_Core", "downloads_sync")

# ── Config por defecto Termux ──
DEFAULT_TERMUX_CONFIG = {
    "ssh_user": "u0_a252",
    "ssh_port": 8022,
    "ssh_key": os.path.expanduser("~/.ssh/id_rsa"),
    "remote_path": "/data/data/com.termux/files/home/ame_core/",
    "sync_enabled": True,
    "sync_interval_minutes": 15
}


def load_termux_config():
    """Carga o crea la configuración Termux desde config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_TERMUX_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_TERMUX_CONFIG)


def save_termux_config(cfg):
    """Guarda la configuración en config.json."""
    full_cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                full_cfg = json.load(f)
        except Exception:
            pass
    for k, v in cfg.items():
        full_cfg[k] = v
    with open(CONFIG_PATH, "w") as f:
        json.dump(full_cfg, f, indent=2)


def ensure_downloads_sync():
    """Crea el directorio downloads_sync si no existe."""
    os.makedirs(SYNC_DEST, exist_ok=True)
    print(f"📁 Directorio de sincronización: {SYNC_DEST}")
    return SYNC_DEST


def get_ssh_target(cfg):
    """Construye usuario@host para SSH."""
    mobile_ip = cfg.get("mobile_ip", "192.168.1.0")
    ssh_user = cfg.get("ssh_user", "u0_a316")
    return f"{ssh_user}@{mobile_ip}"


def sync_via_scp(cfg):
    """
    Sincroniza usando scp -r.
    Descarga todo el contenido de remote_path a downloads_sync/.
    """
    target = get_ssh_target(cfg)
    port = cfg.get("ssh_port", 8022)
    remote = cfg.get("remote_path", "/data/data/com.termux/files/home/ame_core/")
    key = cfg.get("ssh_key", os.path.expanduser("~/.ssh/id_rsa"))

    dest = ensure_downloads_sync()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = os.path.join(dest, f"sync_{timestamp}")
    os.makedirs(batch_dir, exist_ok=True)

    print(f"🔗 [SCP] Conectando a {target}:{port}")
    print(f"📂 Remoto: {remote}")
    print(f"💾 Local:  {batch_dir}")

    cmd = [
        "scp",
        "-P", str(port),
        "-i", key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-r",
        f"{target}:{remote}.",
        batch_dir
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            files = os.listdir(batch_dir)
            print(f"✅ SCP exitoso — {len(files)} archivos descargados")
            for f in files[:20]:  # mostrar primeros 20
                fpath = os.path.join(batch_dir, f)
                size = os.path.getsize(fpath)
                print(f"   📄 {f} ({size/1024:.1f} KB)")
            if len(files) > 20:
                print(f"   ... y {len(files)-20} más")
            return {"status": "ok", "files": len(files), "path": batch_dir}
        else:
            print(f"❌ SCP falló: {result.stderr[:500]}")
            return {"status": "error", "message": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        print("❌ SCP timeout (120s)")
        return {"status": "error", "message": "Timeout"}
    except FileNotFoundError:
        print("❌ scp no encontrado. Instala OpenSSH o usa --mode rsync")
        return {"status": "error", "message": "scp not found"}
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"status": "error", "message": str(e)}


def sync_via_rsync(cfg):
    """
    Sincroniza usando rsync sobre SSH.
    Más rápido para sincronizaciones incrementales.
    """
    target = get_ssh_target(cfg)
    port = cfg.get("ssh_port", 8022)
    remote = cfg.get("remote_path", "/data/data/com.termux/files/home/ame_core/")
    key = cfg.get("ssh_key", os.path.expanduser("~/.ssh/id_rsa"))

    dest = ensure_downloads_sync()

    print(f"🔗 [RSYNC] Conectando a {target}:{port}")
    print(f"📂 Remoto: {remote}")
    print(f"💾 Local:  {dest}")

    # Asegurar que remote termina en / para rsync
    if not remote.endswith("/"):
        remote += "/"

    cmd = [
        "rsync",
        "-avz",
        "--progress",
        "-e", f"ssh -p {port} -i {key} -o StrictHostKeyChecking=no -o ConnectTimeout=10",
        f"{target}:{remote}",
        dest
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            lines = [l for l in result.stdout.split("\n") if l and not l.startswith(".")]
            print(f"✅ RSYNC exitoso")
            print(f"   {lines[-1] if lines else 'completado'}")
            return {"status": "ok", "output": result.stdout[-300:]}
        else:
            print(f"❌ RSYNC falló: {result.stderr[:500]}")
            return {"status": "error", "message": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        print("❌ RSYNC timeout (120s)")
        return {"status": "error", "message": "Timeout"}
    except FileNotFoundError:
        print("❌ rsync no encontrado. Instala rsync o usa --mode scp")
        return {"status": "error", "message": "rsync not found"}
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"status": "error", "message": str(e)}


def test_connection(cfg):
    """Prueba la conexión SSH con Termux."""
    target = get_ssh_target(cfg)
    port = cfg.get("ssh_port", 8022)
    key = cfg.get("ssh_key", os.path.expanduser("~/.ssh/id_rsa"))

    print(f"🧪 Test de conexión a {target}:{port}...")
    cmd = [
        "ssh",
        "-p", str(port),
        "-i", key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        target,
        "echo CONNECTED && uname -a"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(f"✅ Conexión exitosa: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Conexión falló: {result.stderr[:300]}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        return False


# ────────────── CLI ──────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AURA Termux Sync")
    parser.add_argument("--mode", choices=["scp", "rsync", "test"], default="scp",
                        help="Método de sincronización (defecto: scp)")
    parser.add_argument("--ip", help="IP del móvil (opcional, sobreescribe config.json)")
    parser.add_argument("--user", help="Usuario SSH en Termux")
    parser.add_argument("--port", type=int, help="Puerto SSH de Termux")
    args = parser.parse_args()

    cfg = load_termux_config()

    if args.ip:
        cfg["mobile_ip"] = args.ip
        save_termux_config(cfg)
        print(f"📱 IP móvil actualizada: {args.ip}")

    if args.user:
        cfg["ssh_user"] = args.user
        save_termux_config(cfg)

    if args.port:
        cfg["ssh_port"] = args.port
        save_termux_config(cfg)

    print("="*50)
    print("🔁 AURA Termux Sync")
    print(f"📱 Target: {get_ssh_target(cfg)}:{cfg.get('ssh_port', 8022)}")
    print("="*50)

    if args.mode == "test":
        test_connection(cfg)
    elif args.mode == "rsync":
        sync_via_rsync(cfg)
    else:
        sync_via_scp(cfg)