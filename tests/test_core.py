#!/usr/bin/env python3
"""
test_core.py — Tests básicos para el sistema AURA/AME
Verifica que los componentes esenciales funcionan correctamente
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# Añadir directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_version_json_exists():
    """Verifica que version.json existe"""
    version_file = Path(__file__).resolve().parent.parent / "version.json"
    assert version_file.exists(), "version.json no encontrado"
    assert version_file.is_file(), "version.json no es un archivo"


def test_version_json_valid():
    """Verifica que version.json es válido y tiene las versiones esperadas"""
    version_file = Path(__file__).resolve().parent.parent / "version.json"
    with open(version_file) as f:
        versions = json.load(f)

    required_versions = ["aura_core", "ame_client", "godot_game", "protocol"]
    for version in required_versions:
        assert version in versions, f"Versión {version} no encontrada en version.json"

    # Verificar formato de versión
    for version in versions.values():
        parts = version.split(".")
        assert len(parts) == 3, f"Formato de versión incorrecto: {version}"
        assert all(part.isdigit() for part in parts), f"Versión no numérica: {version}"


def test_imports_aura_core():
    """Verifica que los módulos principales de AURA Core se importan correctamente"""
    try:
        import AURA_Core.aura_core
        import AURA_Core.event_manager
        import AURA_Core.godot_bridge

        print("✅ Todos los módulos de AURA Core se importan correctamente")
    except ImportError as e:
        pytest.fail(f"Error importando módulos de AURA Core: {e}")


def test_imports_scripts():
    """Verifica que los scripts principales se importan correctamente"""
    try:
        from scripts import (
            ame_updater,
            auto_updater,
            health_check,
            test_ame_connection,
            version_manager,
        )

        print("✅ Todos los scripts se importan correctamente")
    except ImportError as e:
        pytest.fail(f"Error importando scripts: {e}")


def test_imports_nodes():
    """Verifica que los nodos principales se importan correctamente"""
    try:
        from AURA_Core.nodes.NOD_ROLLERCOIN_BOT import initialize_browser

        print("✅ Nodos principales se importan correctamente")
    except ImportError as e:
        pytest.fail(f"Error importando nodos: {e}")


def test_changelog_exists():
    """Verifica que CHANGELOG.md existe y tiene formato válido"""
    changelog_file = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    assert changelog_file.exists(), "CHANGELOG.md no encontrado"

    with open(changelog_file) as f:
        content = f.read()

    # Verificar que tiene al menos una entrada de versión
    assert "## [" in content, "Formato de versión incorrecto en CHANGELOG.md"
    assert (
        "Añadido" in content or "Cambiado" in content or "Arreglado" in content
    ), "Secciones de cambios no encontradas en CHANGELOG.md"


def test_gitignore_exists():
    """Verifica que .gitignore existe y tiene contenido"""
    gitignore_file = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gitignore_file.exists(), ".gitignore no encontrado"

    with open(gitignore_file) as f:
        content = f.read()

    assert len(content) > 0, ".gitignore está vacío"
    assert "# AURA/AME" in content, "Encabezado incorrecto en .gitignore"


def test_github_workflows():
    """Verifica que los workflows de GitHub existen"""
    workflows_dir = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    assert workflows_dir.exists(), ".github/workflows no encontrado"

    workflow_files = ["test.yml", "notify.yml"]
    for file in workflow_files:
        workflow_file = workflows_dir / file
        assert workflow_file.exists(), f"Workflow {file} no encontrado"

        with open(workflow_file) as f:
            content = f.read()
        assert "name:" in content, f"Workflow {file} no tiene nombre"
        assert "jobs:" in content, f"Workflow {file} no tiene jobs"


def test_health_check_importable():
    """Verifica que health_check.py es importable y tiene funciones esenciales"""
    try:
        from scripts.health_check import check_eventbus, check_godot_bridge, check_python_deps

        print("✅ health_check.py es importable")
    except ImportError as e:
        pytest.fail(f"Error importando health_check: {e}")


def test_version_manager_functions():
    """Verifica que version_manager.py tiene funciones esenciales"""
    try:
        from scripts.version_manager import bump_version, get_changelog, load_versions

        versions = load_versions()
        assert isinstance(versions, dict), "load_versions() no devuelve un diccionario"

        # Verificar que bump_version funciona (sin cambiar realmente la versión)
        test_versions = {"test": "1.0.0"}
        result = bump_version(test_versions, "test", "patch")
        assert result is True, "bump_version() falló"
        assert test_versions["test"] == "1.0.1", "bump_version() no incrementó correctamente"

        print("✅ version_manager.py funciona correctamente")
    except Exception as e:
        pytest.fail(f"Error en version_manager: {e}")


def test_requirements_txt():
    """Verifica que requirements.txt existe y tiene contenido"""
    requirements_file = Path(__file__).resolve().parent.parent / "requirements.txt"
    assert requirements_file.exists(), "requirements.txt no encontrado"

    with open(requirements_file) as f:
        content = f.read()

    assert len(content) > 0, "requirements.txt está vacío"
    assert (
        "websockets" in content or "requests" in content
    ), "Dependencias esenciales no encontradas en requirements.txt"


if __name__ == "__main__":
    # Ejecutar tests manualmente
    print("🧪 Ejecutando tests básicos de AURA/AME...")

    try:
        test_version_json_exists()
        test_version_json_valid()
        test_imports_aura_core()
        test_imports_scripts()
        test_imports_nodes()
        test_changelog_exists()
        test_gitignore_exists()
        test_github_workflows()
        test_health_check_importable()
        test_version_manager_functions()
        test_requirements_txt()

        print("\n🎉 Todos los tests pasaron!")
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ Test falló: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
