"""Automatizador de Compilación y Distribución AURA — Module 30.

Compila la aplicación AURA en binarios ejecutables o bundles distribuibles
utilizando PyInstaller o Nuitka. Incluye copia automatizada de dependencias
nativas, modelos ONNX, DLLs de PyAudio, plantillas de temas Caelestia y manifiestos.

Uso:
    python build_aura.py [--pyinstaller|--nuitka] [--name AURA] [--onedir|--onefile]
"""

from __future__ import annotations

import argparse
import os
import sys
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_DIR = ROOT / "spec"

ENTRYPOINTS = {
    "desktop": ROOT / "frontend" / "aura_hud.py",
    "launcher": ROOT / "main_launcher.py",
    "mobile": ROOT / "mobile_client" / "app.py",
}

ASSETS_TO_COPY = [
    ROOT / "frontend" / "caelestia_theme_engine.py",
    ROOT / "frontend" / "material_widgets.py",
    ROOT / "frontend" / "theme_manager.py",
    ROOT / "frontend" / "webrtc" / "aura_webrtc_client.py",
    ROOT / "frontend" / "webrtc" / "aura_webrtc_utils.py",
    ROOT / "mobile_client" / "network_utils.py",
    ROOT / "backend" / "services" / "audio_pipeline.py",
    ROOT / "backend" / "services" / "tts_engine.py",
    ROOT / "backend" / "services" / "vision_engine.py",
    ROOT / "backend" / "services" / "action_engine.py",
    ROOT / "backend" / "services" / "memory_engine.py",
    ROOT / "backend" / "services" / "swarm_orchestrator.py",
    ROOT / "backend" / "services" / "self_healing.py",
]

THEME_ASSETS = [
    ROOT / "frontend" / "themes",
    ROOT / "frontend" / "assets",
]

MODELS_DIR = ROOT / "models"
NATIVE_LIBS_DIR = ROOT / "native_libs"


def _ensure_dirs() -> None:
    DIST_DIR.mkdir(exist_ok=True)
    BUILD_DIR.mkdir(exist_ok=True)
    SPEC_DIR.mkdir(exist_ok=True)


def _install_build_tool(tool: str) -> None:
    try:
        __import__(tool)
    except ImportError:
        print(f"[cyan]Instalando {tool}...[/cyan]")
        subprocess.check_call([sys.executable, "-m", "pip", "install", tool])


def _collect_assets(dest: Path) -> None:
    for src in ASSETS_TO_COPY:
        if src.exists():
            dest_file = dest / src.name
            if src.is_file():
                shutil.copy2(src, dest_file)
            else:
                if dest_file.exists():
                    shutil.rmtree(dest_file)
                shutil.copytree(src, dest_file)
    for theme_dir in THEME_ASSETS:
        if theme_dir.exists():
            dest_theme = dest / theme_dir.name
            if dest_theme.exists():
                shutil.rmtree(dest_theme)
            shutil.copytree(theme_dir, dest_theme)
    if MODELS_DIR.exists():
        dest_models = dest / "models"
        if dest_models.exists():
            shutil.rmtree(dest_models)
        shutil.copytree(MODELS_DIR, dest_models)
    if NATIVE_LIBS_DIR.exists():
        dest_native = dest / "native_libs"
        if dest_native.exists():
            shutil.rmtree(dest_native)
        shutil.copytree(NATIVE_LIBS_DIR, dest_native)


def _pyinstaller_build(entry: Path, name: str, onefile: bool) -> None:
    _install_build_tool("pyinstaller")
    with tempfile.TemporaryDirectory(prefix="aura_build_") as tmp:
        tmp_path = Path(tmp)
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        for src in ASSETS_TO_COPY:
            if src.exists():
                dst = app_dir / src.name
                if src.is_file():
                    shutil.copy2(src, dst)
                else:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
        for theme_dir in THEME_ASSETS:
            if theme_dir.exists():
                dst = app_dir / theme_dir.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(theme_dir, dst)
        if MODELS_DIR.exists():
            dst = app_dir / "models"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(MODELS_DIR, dst)
        if NATIVE_LIBS_DIR.exists():
            dst = app_dir / "native_libs"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(NATIVE_LIBS_DIR, dst)

        spec_name = f"{name}.spec"
        cmd = [
            sys.executable, "-m", "PyInstaller",
            str(entry),
            "--name", name,
            "--distpath", str(DIST_DIR / name),
            "--workpath", str(BUILD_DIR / name),
            "--specpath", str(SPEC_DIR),
            "--clean",
            "--noconfirm",
        ]
        if onefile:
            cmd.append("--onefile")
        else:
            cmd.append("--onedir")
        cmd.extend(["--add-data", f"{app_dir}{os.pathsep}aura_app_data"])
        if platform.system() == "Windows":
            cmd.extend(["--icon", str(ROOT / "assets" / "icon.ico")])
        else:
            cmd.extend(["--icon", str(ROOT / "assets" / "icon.png")])
        print(f"[cyan]Compilando con PyInstaller: {' '.join(cmd)}[/cyan]")
        subprocess.check_call(cmd)


def _nuitka_build(entry: Path, name: str) -> None:
    _install_build_tool("nuitka")
    cmd = [
        sys.executable, "-m", "nuitka",
        str(entry),
        "--output-dir", str(DIST_DIR),
        "--output-filename", f"{name}.exe" if platform.system() == "Windows" else name,
        "--remove-output",
        "--standalone",
        "--onefile",
        "--include-package=backend",
        "--include-package=frontend",
        "--include-package=mobile_client",
        "--include-data-dir", f"{ROOT / 'frontend'}=frontend",
        "--include-data-dir", f"{ROOT / 'backend'}=backend",
        "--include-data-dir", f"{ROOT / 'mobile_client'}=mobile_client",
    ]
    print(f"[cyan]Compilando con Nuitka: {' '.join(cmd)}[/cyan]")
    subprocess.check_call(cmd)


def build(target: str = "desktop", tool: str = "pyinstaller", onefile: bool = True) -> None:
    _ensure_dirs()
    entry = ENTRYPOINTS.get(target)
    if not entry or not entry.exists():
        print(f"[red]ERROR: Entrypoint no válido: {target}[/red]")
        sys.exit(1)
    name = f"AURA_{target}"
    if tool == "nuitka":
        _nuitka_build(entry, name)
    else:
        _pyinstaller_build(entry, name, onefile=onefile)
    print(f"[green]✓ Build completado en: {DIST_DIR / name}[/green]")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AURA Build Script")
    parser.add_argument("--target", choices=["desktop", "launcher", "mobile"], default="desktop")
    parser.add_argument("--tool", choices=["pyinstaller", "nuitka"], default="pyinstaller")
    parser.add_argument("--onedir", action="store_true", help="Build en carpeta (no onefile)")
    args = parser.parse_args(argv)
    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    build(target=args.target, tool=args.tool, onefile=not args.onedir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
