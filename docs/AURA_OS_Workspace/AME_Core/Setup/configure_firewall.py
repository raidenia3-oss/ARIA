#!/usr/bin/env python3
"""
Script para configurar el Firewall de Windows y permitir tráfico en el puerto 11434.
"""

import subprocess
import sys

def configure_firewall():
    """Añade una regla al Firewall de Windows para permitir tráfico en el puerto 11434."""
    try:
        print("🔒 Configurando Firewall de Windows para permitir acceso al puerto 11434...")

        # Verificar si la regla ya existe
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "protocol=TCP", "localport=11434"],
            capture_output=True,
            text=True
        )

        if "No rules match the specified criteria" in result.stdout:
            # Crear una nueva regla para permitir el tráfico en el puerto 11434
            subprocess.run([
                "netsh", "advfirewall", "firewall", "add", "rule",
                "name=OllamaRemoteAccess",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                "localport=11434",
                "description=Permitir acceso remoto a Ollama"
            ], check=True)
            print("✅ Regla de Firewall añadida para permitir acceso al puerto 11434.")
        else:
            print("✅ La regla de Firewall ya existe para el puerto 11434.")

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al configurar Firewall: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def main():
    """Función principal para configurar el Firewall."""
    print("=" * 50)
    print("🔒 Configurando Firewall para Ollama Remote Access")
    print("=" * 50)

    if not configure_firewall():
        print("⚠️  No se pudo configurar el Firewall.")

    print("\n🔒 Configuración de Firewall completada.")
    print("=" * 50)

if __name__ == "__main__":
    main()