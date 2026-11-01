#!/usr/bin/env bash
set -euo pipefail

# aria-start.sh — Lanzador de ARIA OS nativo en Kali Linux
# Se invoca desde .desktop autostart o manualmente.

source /opt/aria/venv/bin/activate
cd /opt/aria/ARIA_APP

# Crear directorio de logs si no existe
mkdir -p /var/log/aria

# Ejecutar ARIA con logging a archivo y stdout
exec python ARIA_APP/aria_native.py >> /var/log/aria/aria.log 2>&1
