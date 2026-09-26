"""
run_shadow.py - Iniciador del Shadow-Core + Security Shield
Ejecuta el servidor en el puerto 5001 con protección activa.
"""

import sys
import os

# Añadir AME_Core al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "AME_Core"))

from shadow_core import start_shadow_core

if __name__ == "__main__":
    print("🚀 Iniciando Shadow-Core en puerto 5001...")
    print("🛡️  Security Shield activo")
    start_shadow_core()