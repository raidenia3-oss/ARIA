#!/usr/bin/env python3
"""
Script para configurar Loki como sistema de logs centralizados.
"""

import os
import subprocess
import json
import time
from pathlib import Path

def setup_loki():
    """Configura Loki para almacenar logs centralizados."""
    try:
        print("🔧 Configurando Loki para logs centralizados...")

        # Crear directorio para Loki
        loki_dir = Path("AURA_Core/loki")
        loki_dir.mkdir(exist_ok=True)

        # Configuración de Loki
        loki_config = {
            "auth_enabled": False,
            "server": {
                "http_listen_port": 3100,
                "grpc_listen_port": 9096
            },
            "common": {
                "path_prefix": "/loki",
                "storage": {
                    "filesystem": {
                        "chunks_directory": "/loki/chunks",
                        "rules_directory": "/loki/rules"
                    }
                }
            },
            "schema_config": {
                "configs": [
                    {
                        "from": "2020-10-24",
                        "store": "boltdb-shipper",
                        "object_store": "filesystem",
                        "schema": "v11",
                        "index": {
                            "prefix": "index_",
                            "period": "24h"
                        }
                    }
                ]
            },
            "ruler": {
                "alertmanager_url": ""
            },
            "limits_config": {
                "enforce_metric_name": "",
                "reject_old_samples": True,
                "reject_old_samples_max_age": "168h"
            }
        }

        # Crear archivo de configuración de Loki
        config_path = loki_dir / "loki-config.yaml"
        with open(config_path, "w") as f:
            for key, value in loki_config.items():
                if isinstance(value, dict):
                    f.write(f"{key}:\n")
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, dict):
                            f.write(f"  {subkey}:\n")
                            for subsubkey, subsubvalue in subvalue.items():
                                f.write(f"    {subsubkey}: {subsubvalue}\n")
                        else:
                            f.write(f"  {subkey}: {subvalue}\n")
                else:
                    f.write(f"{key}: {value}\n")

        # Crear script para iniciar Loki
        start_loki_script = loki_dir / "start_loki.sh"
        with open(start_loki_script, "w") as f:
            f.write("""
#!/bin/bash
# Script para iniciar Loki

echo "🔧 Iniciando Loki..."
docker run -d \
  --name=loki \
  -p 3100:3100 \
  -v $(pwd)/loki-config.yaml:/etc/loki/loki-config.yaml \
  -v $(pwd)/chunks:/loki/chunks \
  -v $(pwd)/rules:/loki/rules \
  grafana/loki:latest
""")

        # Crear script para enviar logs a Loki
        log_forwarder_script = loki_dir / "log_forwarder.py"
        with open(log_forwarder_script, "w") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("# Forwarder para enviar logs a Loki.\n")
            f.write("\n")
            f.write("""
import requests
import time
import logging
import os
from logging.handlers import HTTPHandler

# Configuración de Loki
LOKI_URL = "http://localhost:3100/loki/api/v1/push"
LOKI_USER = ""
LOKI_PASSWORD = ""

# Configurar logging para enviar logs a Loki
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        HTTPHandler(
            LOKI_URL,
            url=LOKI_URL,
            method="POST",
            headers={"Content-Type": "application/json"},
            formatter=logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        )
    ]
)

# Ejemplo de uso
if __name__ == "__main__":
    logger = logging.getLogger("aura_logs")
    while True:
        logger.info("Ejemplo de log de AURA")
        time.sleep(5)
""")

        print("✅ Configuración de Loki guardada en AURA_Core/loki/")
        print("📌 Instrucciones:")
        print("   1. Ejecuta el script start_loki.sh para iniciar el contenedor de Loki.")
        print("   2. Usa el script log_forwarder.py para enviar logs a Loki.")
        print("   3. Accede a Kibana o Grafana para visualizar los logs.")

        return True
    except Exception as e:
        print(f"❌ Error al configurar Loki: {e}")
        return False

def main():
    """Función principal para configurar Loki."""
    print("=" * 50)
    print("📊 Configurando Loki para logs centralizados")
    print("=" * 50)

    if not setup_loki():
        print("⚠️  No se pudo configurar Loki.")

    print("\n📊 Configuración de Loki completada.")
    print("=" * 50)

if __name__ == "__main__":
    main()