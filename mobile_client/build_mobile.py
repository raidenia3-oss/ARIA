"""AURA Mobile Client — Script de empaquetado multiplataforma.

Genera builds de la aplicacion Flet:
- Web/PWA estatica:  flet build web
- Android APK:       flet build apk

Incluye manifiesto PWA, icono del sistema y copia de assets.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
WEB_BUILD = ROOT / "build" / "web"
APK_BUILD = ROOT / "build" / "apk"


def _ensure_flet() -> None:
    try:
        import flet  # noqa: F401
    except ImportError:
        print("Flet no encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flet"])


def _prepare_assets() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not (ASSETS / "icon.png").exists():
        print("Advertencia: assets/icon.png no encontrado. El build usara el icono por defecto de Flet.")
    if not (ASSETS / "manifest.json").exists():
        manifest = {
            "name": "AURA Mobile",
            "short_name": "AURA",
            "start_url": ".",
            "display": "standalone",
            "background_color": "#0f0f1a",
            "theme_color": "#6366f1",
            "icons": [
                {"src": "icon.png", "sizes": "192x192", "type": "image/png"},
                {"src": "icon.png", "sizes": "512x512", "type": "image/png"},
            ],
        }
        import json
        (ASSETS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("Creado assets/manifest.json por defecto.")


def _ensure_flutter() -> None:
    try:
        subprocess.run(
            ["flutter", "--version"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        print("Error: Flutter SDK no encontrado en PATH.")
        print("Instala Flutter 3.22+ desde https://flutter.dev/docs/get-started/install")
        print("Luego agrega flutter/bin a tu PATH y vuelve a ejecutar este script.")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"Error al verificar Flutter SDK: {exc.stderr}")
        sys.exit(1)


def _flet_cmd() -> str:
    flet_exe = shutil.which("flet")
    if flet_exe:
        return flet_exe
    fallback = Path(sys.executable).parent / "Scripts" / "flet.exe"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError("No se encontro el ejecutable 'flet'. Instala flet-cli con: pip install flet")


def _subprocess_env():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["CHCP"] = "65001"
    return env


def build_web() -> None:
    _ensure_flet()
    _ensure_flutter()
    _prepare_assets()
    print("Compilando AURA Mobile para Web/PWA...")
    cmd = [_flet_cmd(), "build", "web", str(ROOT / "app.py")]
    subprocess.check_call(cmd, cwd=str(ROOT), env=_subprocess_env(), encoding="utf-8", errors="replace")
    _copy_assets_to(WEB_BUILD)


def build_apk() -> None:
    _ensure_flet()
    _ensure_flutter()
    _prepare_assets()
    print("Compilando AURA Mobile para Android APK...")
    build_dir = ROOT / "build_android"
    cmd = [
        _flet_cmd(),
        "build",
        "apk",
        str(ROOT / "app.py"),
        "--project-name",
        "aura_launcher",
        "--build-dir",
        str(build_dir),
    ]
    subprocess.check_call(cmd, cwd=str(ROOT), env=_subprocess_env(), encoding="utf-8", errors="replace")
    _copy_assets_to(build_dir)


def _copy_assets_to(build_dir: Path) -> None:
    if build_dir.exists():
        dest = build_dir / "assets"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(ASSETS, dest)
        if (ASSETS / "manifest.json").exists():
            shutil.copy(ASSETS / "manifest.json", build_dir / "manifest.json")
        if (ASSETS / "icon.png").exists():
            shutil.copy(ASSETS / "icon.png", build_dir / "icon.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="AURA Mobile Build Script")
    parser.add_argument("--web", action="store_true", help="Build Web/PWA")
    parser.add_argument("--apk", action="store_true", help="Build Android APK")
    args = parser.parse_args()

    if not args.web and not args.apk:
        parser.print_help()
        sys.exit(1)

    if args.web:
        build_web()
    if args.apk:
        build_apk()


if __name__ == "__main__":
    main()
