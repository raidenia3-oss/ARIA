#!/usr/bin/env python3
"""
version_manager.py — Maneja versiones de AURA/AME
Gestiona versiones de todos los componentes y genera changelogs
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

# Configuración
VERSION_FILE = Path(__file__).resolve().parent.parent / "version.json"
CHANGELOG_FILE = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
GODOT_VERSION_FILE = Path(__file__).resolve().parent.parent / "godot_game" / "version.txt"

# Versiones por defecto
DEFAULT_VERSIONS = {
    "aura_core": "1.0.0",
    "ame_client": "1.0.0",
    "godot_game": "1.0.0",
    "protocol": "1.0.0"
}

def load_versions():
    """Carga versiones desde version.json o usa valores por defecto"""
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE) as f:
                return json.load(f)
        except Exception:
            print("⚠️  Error cargando version.json. Usando valores por defecto.")
    return DEFAULT_VERSIONS

def save_versions(versions):
    """Guarda versiones en version.json"""
    try:
        with open(VERSION_FILE, 'w') as f:
            json.dump(versions, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error guardando version.json: {e}")
        return False

def bump_version(versions, component, level="patch"):
    """
    Incrementa versión de un componente
    level: "patch" (1.0.0→1.0.1), "minor" (1.0.0→1.1.0), "major" (1.0.0→2.0.0)
    """
    if component not in versions:
        print(f"❌ Componente '{component}' no encontrado en versiones")
        return False

    current = versions[component]
    parts = list(map(int, current.split('.')))

    if level == "patch":
        parts[2] += 1
    elif level == "minor":
        parts[1] += 1
        parts[2] = 0
    elif level == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    else:
        print(f"❌ Nivel de versión inválido: {level}")
        return False

    new_version = ".".join(map(str, parts))
    versions[component] = new_version

    # Guardar versión actualizada
    if save_versions(versions):
        print(f"✅ Versión actualizada: {component} → {new_version}")

        # Actualizar Godot version.txt
        if component == "godot_game":
            update_godot_version(new_version)

        return True
    return False

def update_godot_version(version):
    """Actualiza version.txt en godot_game"""
    try:
        GODOT_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        GODOT_VERSION_FILE.write_text(f"Godot Game Version: {version}\n")
        print(f"✅ Godot version.txt actualizado: {version}")
    except Exception as e:
        print(f"❌ Error actualizando Godot version.txt: {e}")

def get_changelog(entries=5):
    """Obtiene las últimas N entradas del changelog"""
    if not CHANGELOG_FILE.exists():
        return []

    try:
        with open(CHANGELOG_FILE) as f:
            content = f.read()

        # Buscar secciones de versión
        sections = re.findall(r"## \[.*?\] - \d{4}-\d{2}-\d{2}\n(.*?)(?=## \[|$)", content, re.DOTALL)
        return sections[-entries:] if sections else []
    except Exception as e:
        print(f"❌ Error leyendo CHANGELOG.md: {e}")
        return []

def add_changelog_entry(versions, changes):
    """
    Añade una nueva entrada al changelog
    changes: dict con claves "added", "changed", "fixed"
    """
    if not CHANGELOG_FILE.exists():
        # Crear changelog si no existe
        initial_content = """# Changelog

## [1.0.0] - 2026-06-03
### Añadido
- EventBus WebSocket inicial
- AURABridge.gd para Godot
- Cloudflare Tunnel gratuito via trycloudflare.com

### Cambiado
- (nada aún)

### Arreglado
- (nada aún)
"""
        CHANGELOG_FILE.write_text(initial_content)

    # Obtener la última versión del changelog
    last_version = None
    with open(CHANGELOG_FILE) as f:
        content = f.read()
        match = re.search(r"## \[(.*?)\] - (\d{4}-\d{2}-\d{2})", content)
        if match:
            last_version = match.group(1)
            last_date = match.group(2)

    # Usar la versión más reciente o la primera
    if not last_version:
        last_version = "1.0.0"
        last_date = "2026-06-03"

    # Determinar nueva versión
    new_version = max(versions.values())
    new_date = datetime.now().strftime("%Y-%m-%d")

    # Crear nueva entrada
    entry = f"""
## [{new_version}] - {new_date}
### Añadido
{format_changes(changes.get("added", []))}

### Cambiado
{format_changes(changes.get("changed", []))}

### Arreglado
{format_changes(changes.get("fixed", []))}
"""

    # Añadir al principio del archivo
    try:
        with open(CHANGELOG_FILE, 'r+') as f:
            content = f.read()
            f.seek(0)
            f.write(entry + "\n" + content)
        print(f"✅ Nueva entrada añadida al changelog: {new_version}")
        return True
    except Exception as e:
        print(f"❌ Error añadiendo entrada al changelog: {e}")
        return False

def format_changes(changes):
    """Formatea cambios para el changelog"""
    if not changes:
        return "- (nada aún)"

    return "\n".join([f"- {change}" for change in changes])

def check_for_updates():
    """Compara versiones locales con las del repositorio (simulado)"""
    # En un entorno real, esto haría una petición a GitHub API
    # Por ahora, solo muestra las versiones actuales
    versions = load_versions()
    print("\n🔍 Versiones actuales:")
    for component, version in versions.items():
        print(f"   {component:15s}: {version}")

    # Ejemplo de comparación (simulada)
    print("\n🔄 Comparación con repositorio (simulada):")
    print("   (En un entorno real, esto consultaría GitHub API)")
    print("   Ejemplo: python version_manager.py check_updates --remote")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AURA/AME Version Manager")
    parser.add_argument("command", choices=["bump", "show", "changelog", "check_updates"])
    parser.add_argument("--component", help="Componente para actualizar (aura_core, ame_client, godot_game, protocol)")
    parser.add_argument("--level", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--changes", nargs="+", help="Cambios para añadir al changelog (ej: 'nuevo bot rollercoin')")
    parser.add_argument("--remote", action="store_true", help="Verificar actualizaciones remotas (simulado)")

    args = parser.parse_args()

    if args.command == "bump":
        if not args.component:
            print("❌ Debes especificar --component")
            return

        versions = load_versions()
        if bump_version(versions, args.component, args.level):
            # Preguntar si quiere añadir cambios al changelog
            if args.changes:
                changes = {
                    "added": args.changes
                }
                add_changelog_entry(versions, changes)
            else:
                print("\n¿Quieres añadir cambios al changelog? (y/n)")
                if input().lower() == 'y':
                    changes = {"added": []}
                    print("Ingresa los cambios (uno por línea, Ctrl+D para terminar):")
                    while True:
                        try:
                            change = input()
                            if change:
                                changes["added"].append(change)
                        except EOFError:
                            break
                    add_changelog_entry(versions, changes)

    elif args.command == "show":
        versions = load_versions()
        print("\n📋 Versiones actuales:")
        for component, version in versions.items():
            print(f"   {component:15s}: {version}")

    elif args.command == "changelog":
        entries = get_changelog()
        if entries:
            print("\n📜 Últimas entradas del changelog:")
            for i, entry in enumerate(entries, 1):
                print(f"\n--- Entrada {i} ---")
                print(entry)
        else:
            print("⚠️  No hay entradas en el changelog aún")

    elif args.command == "check_updates":
        check_for_updates()

if __name__ == "__main__":
    main()