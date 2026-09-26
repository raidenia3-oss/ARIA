#!/usr/bin/env python3
"""
AURA OS Bootstrap
Configura Arch Linux para funcionar como AURA OS Desktop Environment.

Uso:
    sudo python3 bootstrap_aura_os.py
"""

from __future__ import annotations

import os
import sys
import subprocess
import shutil
from pathlib import Path


AURA_OS_ROOT = Path(__file__).resolve().parent.parent
SYSTEMD_DIR = AURA_OS_ROOT / "aura-os" / "systemd"
ETC_DIR = AURA_OS_ROOT / "aura-os" / "etc"
OPT_AURA = Path("/opt/aura")


def run(cmd: list[str], check: bool = True) -> None:
    print(f"[Bootstrap] Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)


def ensure_user(username: str) -> None:
    try:
        subprocess.run(["id", username], check=True, capture_output=True)
        print(f"[Bootstrap] Usuario {username} ya existe")
    except subprocess.CalledProcessError:
        print(f"[Bootstrap] Creando usuario {username}...")
        run(["useradd", "--create-home", "--shell", "/bin/bash", username])
        run(["usermod", "-aG", "wheel", username])
        run(["chown", "-R", f"{username}:{username}", f"/home/{username}"])


def install_packages() -> None:
    print("[Bootstrap] Instalando dependencias core...")
    packages = [
        "hyprland",
        "wayland",
        "waybar",
        "rofi-wayland",
        "kitty",
        "pipewire",
        "pipewire-pulse",
        "python",
        "python-pip",
        "git",
        "ufw",
        "brightnessctl",
        "postgresql",
        "redis",
    ]
    run(["pacman", "-S", "--noconfirm"] + packages)


def setup_aura_backend() -> None:
    print("[Bootstrap] Configurando AURA backend...")
    OPT_AURA.mkdir(parents=True, exist_ok=True)
    run(["cp", "-r", str(AURA_OS_ROOT / "backend"), str(OPT_AURA / "backend")])
    run(["cp", "-r", str(AURA_OS_ROOT / "scripts"), str(OPT_AURA / "scripts")])
    run(["cp", "-r", str(AURA_OS_ROOT / "godot"), str(OPT_AURA / "godot")])

    venv = OPT_AURA / "venv"
    run([sys.executable, "-m", "venv", str(venv)])
    pip = venv / "bin" / "pip"
    run([str(pip), "install", "-r", str(AURA_OS_ROOT / "backend" / "requirements.txt")])


def install_systemd_services() -> None:
    print("[Bootstrap] Instalando systemd services...")
    systemd_target = Path("/etc/systemd/system")
    for svc in SYSTEMD_DIR.glob("*.service"):
        run(["cp", str(svc), str(systemd_target / svc.name)])
    for target in SYSTEMD_DIR.glob("*.target"):
        run(["cp", str(target), str(systemd_target / target.name)])
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "aura-brain.service"])
    run(["systemctl", "enable", "--now", "aura-shell.service"])


def setup_hyprland() -> None:
    print("[Bootstrap] Configurando Hyprland...")
    home = Path("/home/aura")
    config = home / ".config" / "hypr" / "hyprland.conf"
    config.parent.mkdir(parents=True, exist_ok=True)

    conf = f"""
# AURA OS Hyprland Config
monitor=,preferred,auto,1

exec-once = /opt/aura/aura_shell_linux.x86_64 --no-window --fullscreen
exec-once = waybar

windowrule = float, ^(aura_shell)$
windowrule = noborder, ^(aura_shell)$
windowrule = fullscreen, ^(aura_shell)$
windowrule = opacity 0.9 0.9, ^(aura_shell)$

bind = SUPER, Q, exec, kitty
bind = SUPER, C, killactive,
bind = SUPER, M, exit,
"""
    config.write_text(conf, encoding="utf-8")
    run(["chown", "-R", "aura:aura", str(home)])


def setup_aura_env() -> None:
    print("[Bootstrap] Configurando variables de entorno...")
    env_file = Path("/etc/aura/aura.env")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    src = AURA_OS_ROOT / "backend" / ".env"
    if src.exists():
        run(["cp", str(src), str(env_file)])
    else:
        env_file.write_text("AURA_BACKEND_URL=http://localhost:8000\n", encoding="utf-8")


def main() -> int:
    if os.geteuid() != 0:
        print("[Bootstrap] Ejecutar como root: sudo python3 bootstrap_aura_os.py")
        return 1

    print("[Bootstrap] Iniciando configuración de AURA OS...")
    ensure_user("aura")
    install_packages()
    setup_aura_backend()
    setup_aura_env()
    install_systemd_services()
    setup_hyprland()
    print("[Bootstrap] AURA OS bootstrap completo. Reinicia para iniciar Hyprland.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
