#!/usr/bin/env python3
"""
Script de prueba para verificar el entorno de GBrain
"""

import sys
import os
from pathlib import Path

# Añadir el directorio actual al PATH
sys.path.append(str(Path.cwd()))

# Verificar que los módulos necesarios estén disponibles
required_modules = [
    'sentence_transformers',
    'networkx',
    'markdown',
    'numpy',
    'sklearn',
    'watchdog'
]

print("Verificando módulos necesarios para GBrain:")
print("=" * 50)

for module in required_modules:
    try:
        __import__(module)
        print(f"✅ {module}: Disponible")
    except ImportError:
        print(f"❌ {module}: No disponible")

print("\nVerificando estructura de directorios:")
print("=" * 50)

# Verificar estructura de la bóveda
vault_path = Path("AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT")
if vault_path.exists():
    print(f"✅ Bóveda de conocimiento encontrada en: {vault_path}")
    print(f"   Contenido: {list(vault_path.iterdir())[:5]}...")  # Mostrar primeros 5 elementos
else:
    print(f"❌ Bóveda de conocimiento no encontrada en: {vault_path}")
    print("   Creando estructura...")
    vault_path.mkdir(parents=True, exist_ok=True)
    print(f"   Estructura creada en: {vault_path}")

# Verificar archivos de configuración
config_path = Path("AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json")
if config_path.exists():
    print(f"✅ Configuración de GBrain encontrada en: {config_path}")
else:
    print(f"❌ Configuración de GBrain no encontrada en: {config_path}")

# Verificar scripts de integración
scripts_dir = Path("AME_EXPORT_PACKAGE/scripts")
if scripts_dir.exists():
    print(f"✅ Directorio de scripts encontrado en: {scripts_dir}")
    print(f"   Scripts disponibles: {list(scripts_dir.glob('*.py'))}")
else:
    print(f"❌ Directorio de scripts no encontrado en: {scripts_dir}")

print("\nVerificando rutas de importación:")
print("=" * 50)

# Verificar rutas de importación
sys.path.insert(0, str(Path.cwd() / "AME_EXPORT_PACKAGE"))
sys.path.insert(0, str(Path.cwd() / "AME_EXPORT_PACKAGE/TERMUX_AGENT/core"))

try:
    # Intentar importar los módulos de GBrain
    from gbrain_orchestrator import GBrainOrchestrator
    print("✅ Módulo gbrain_orchestrator: Importado correctamente")
except ImportError as e:
    print(f"❌ Módulo gbrain_orchestrator: {str(e)}")

try:
    # Intentar importar las utilidades
    from gbrain_utils import GBrainUtils
    print("✅ Módulo gbrain_utils: Importado correctamente")
except ImportError as e:
    print(f"❌ Módulo gbrain_utils: {str(e)}")

print("\nVerificación completada.")
print("=" * 50)
print("Si todos los módulos están disponibles y las rutas son correctas,")
print("el entorno está listo para ejecutar el servidor con integración GBrain.")