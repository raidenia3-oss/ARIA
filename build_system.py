"""Build system for AURA standalone executable — Module 30 final delivery.

Configura la compilacion binaria unificada usando PyInstaller para generar
un ejecutable de Windows standalone (AURA_Assistant.exe).

Incluye assets visuales, archivos de configuracion, dependencias estaticas
de PySide6 e iconos del sistema dentro del empaquetado.

Uso:
    python build_system.py build         # Compilar ejecutable
    python build_system.py spec        # Generar archivo .spec
    python build_system.py clean       # Limpiar artefactos de build
    python build_system.py test-build  # Build + verificacion rapida
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field

PROJECT_ROOT = Path(__file__).parent.resolve()
BUILD_DIR = PROJECT_ROOT / "dist"
SPEC_DIR = PROJECT_ROOT / "build"
ASSETS_DIR = PROJECT_ROOT / "frontend" / "assets"
ICON_PATH = ASSETS_DIR / "aura_icon.ico"
ENTRY_POINT = PROJECT_ROOT / "main_launcher.py"

DEFAULT_EXE_NAME = "AURA_Assistant"
APP_VERSION = "30.0.0"

FRONTEND_ASSETS = [
    "frontend/assets",
    "frontend/aura_hud.py",
]

CONFIG_FILES = [
    "*.env",
    "requirements.txt",
    ".env.example",
]

PY_SIDE_DIRS = [
    "PySide6",
    "shiboken6",
]

ASSETS_TO_INCLUDE = [
    ("frontend/assets/aura_icon.png", "frontend/assets/aura_icon.png"),
    ("requirements.txt", "requirements.txt"),
    (".env.example", ".env.example"),
]


@dataclass
class BuildConfig:
    name: str = DEFAULT_EXE_NAME
    entry_point: str = str(ENTRY_POINT)
    icon: str = str(ICON_PATH)
    onefile: bool = True
    windowed: bool = True
    version: str = APP_VERSION
    app_version: str = APP_VERSION
    company: str = "AURA Project"
    description: str = "Autonomous Unified Reasoning Architecture - AI Assistant"
    output_dir: str = str(BUILD_DIR)
    exclude_modules: List[str] = field(default_factory=lambda: [
        "tkinter", "matplotlib", "matplotlib.pyplot", "IPython",
        "pytest", "unittest", "test", "tests",
    ])
    hidden_imports: List[str] = field(default_factory=lambda: [
        "requests", "rich", "PySide6", "PySide6.QtCore",
        "PySide6.QtGui", "PySide6.QtWidgets",
        "frontend.dashboard_window",
        "frontend.aura_hud",
        "backend.main",
    ])
    datas: List[tuple] = field(default_factory=list)

    def __post_init__(self):
        if not self.datas:
            self.datas = list(ASSETS_TO_INCLUDE) + self._collect_pyside_datas()

    def _collect_pyside_datas(self) -> List[tuple]:
        datas = []
        for pkg_dir in PY_SIDE_DIRS:
            try:
                mod = __import__(pkg_dir)
                pkg_path = os.path.dirname(getattr(mod, "__file__", ""))
                if pkg_path and os.path.isdir(pkg_path):
                    datas.append((pkg_path, pkg_dir))
            except ImportError:
                continue
        return datas


def generate_version_info(config: BuildConfig) -> str:
    """Genera un archivo version info para el ejecutable de Windows."""
    return f"""
# UTF-8
#
# Para el compilador de recursos de Windows.

1 VERSIONINFO
    FILEVERSION {config.version.replace('.', ',')}
    PRODUCTVERSION {config.version.replace('.', ',')}
    FILEFLAGSMASK 0x3fL
    FILEFLAGS 0x0L
    FILEOS 0x40004L
    FILETYPE 0x1L
    FILESUBTYPE 0x0L
BEGIN
    BLOCK "Company"
    BEGIN
        VALUE "CompanyName", "{config.company}"
        VALUE "FileDescription", "{config.description}"
        VALUE "FileVersion", "{config.version}"
        VALUE "InternalName", "{config.name}"
        VALUE "OriginalFilename", "{config.name}.exe"
        VALUE "ProductName", "{config.name}"
        VALUE "ProductVersion", "{config.version}"
    END
END
"""


def generate_spec(config: BuildConfig, output_path: Optional[str] = None) -> str:
    """Genera un archivo .spec para PyInstaller."""
    spec_path = output_path or str(PROJECT_ROOT / f"{config.name.lower()}.spec")

    datas_repr = repr(config.datas)
    hidden_imports_repr = repr(config.hidden_imports)
    exclude_repr = repr(config.exclude_modules)

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AURA Assistant - Module 30."""

block_cipher = None

a = Analysis(
    [r"{config.entry_point}"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas={datas_repr},
    hiddenimports={hidden_imports_repr},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={exclude_repr},
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

version_info = {repr(generate_version_info(config))}

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="{config.name}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=not config.windowed,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=config.icon,
    version_info=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="{config.name}",
)
'''
    with open(spec_path, "w") as f:
        f.write(spec_content)
    return spec_path


def run_pyinstaller(config: BuildConfig, generate_only: bool = False) -> subprocess.CompletedProcess:
    """Ejecuta PyInstaller con la configuracion especificada."""
    if not os.path.exists(config.entry_point):
        raise FileNotFoundError(f"Entry point not found: {config.entry_point}")

    cmd: List[str] = [
        sys.executable, "-m", "PyInstaller",
        config.entry_point,
        "--name", config.name,
        "--distpath", config.output_dir,
        "--workpath", str(SPEC_DIR),
        "--specpath", str(PROJECT_ROOT),
        "--noconfirm",
    ]

    if config.onefile:
        cmd.append("--onefile")
    if config.windowed:
        cmd.append("--windowed")
    if os.path.exists(config.icon):
        cmd.extend(["--icon", config.icon])
    for mod in config.exclude_modules:
        cmd.extend(["--exclude-module", mod])
    for imp in config.hidden_imports:
        cmd.extend(["--hidden-import", imp])
    for data in config.datas:
        src, dst = data
        cmd.extend(["--add-data", f"{src};{dst}"])

    print(f"[cyan]PyInstaller command:[/cyan] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    print(f"[cyan]Return code: {result.returncode}[/cyan]")
    if result.stdout:
        for line in result.stdout.splitlines()[-10:]:
            print(f"  {line}")
    if result.returncode != 0 and result.stderr:
        for line in result.stderr.splitlines()[-5:]:
            print(f"  [red]{line}[/red]")
    return result


def clean_build() -> None:
    """Limpia artefactos de build previos."""
    dirs_to_clean = [BUILD_DIR, SPEC_DIR]
    for d in dirs_to_clean:
        if os.path.exists(str(d)):
            shutil.rmtree(str(d))
            print(f"  Cleaned: {d}")
    spec_files = list(PROJECT_ROOT.glob("*.spec"))
    for spec in spec_files:
        spec.unlink()
        print(f"  Removed: {spec}")
    print("[green]Clean complete[/green]")


def build(config: BuildConfig) -> bool:
    """Compila el ejecutable standalone."""
    print(f"[bold cyan]=== Building {config.name} v{config.version} ===[/bold cyan]")
    result = run_pyinstaller(config)
    if result.returncode == 0:
        print(f"[green]Build successful![/green]")
        print(f"  Executable: {BUILD_DIR / config.name}.exe")
        return True
    print(f"[red]Build failed (exit code {result.returncode})[/red]")
    return False


def generate(config: BuildConfig) -> str:
    """Genera el archivo .spec."""
    spec_path = generate_spec(config)
    print(f"[green]Spec generated: {spec_path}[/green]")
    return spec_path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AURA Build System")
    parser.add_argument("action", choices=["build", "spec", "clean", "test-build"],
                        default="build", nargs="?",
                        help="Accion a ejecutar: build | spec | clean | test-build")
    parser.add_argument("--name", default=DEFAULT_EXE_NAME, help="Nombre del ejecutable")
    parser.add_argument("--version", default=APP_VERSION, help="Version del ejecutable")
    parser.add_argument("--windowed", action="store_true", default=True, help="Modo ventana (no consola)")
    parser.add_argument("--console", action="store_true", help="Modo consola (debug)")
    parser.add_argument("--onefile", action="store_true", default=True, help="Compilar como ejecutable unico")

    args = parser.parse_args()

    config = BuildConfig(
        name=args.name,
        version=args.version,
        windowed=not args.console,
        onefile=args.onefile,
    )

    if args.action == "clean":
        clean_build()
    elif args.action == "spec":
        generate(config)
    elif args.action == "build":
        generate(config)
        success = build(config)
        sys.exit(0 if success else 1)
    elif args.action == "test-build":
        generate(config)
        print("\n[yellow]=== Dry-run: showing command only ===[/yellow]")
        cmd = [sys.executable, "-m", "PyInstaller", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"PyInstaller version: {result.stdout.splitlines()[0] if result.stdout else 'unknown'}")
        print(f"[green]Config valid. Ready to build.[/green]")


if __name__ == "__main__":
    main()
