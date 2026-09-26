#!/data/data/com.termux/files/usr/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# install_ame.sh - Instalador unificado del Agente AME para Termux
# Ejecutar: bash install_ame.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

AURA_BASE="/data/data/com.termux/files/home"
AME_DIR="${AURA_BASE}/AME-termux"
MODULES_DIR="${AURA_BASE}/AME_EXPORT_PACKAGE/modules"
HOOKS_DIR="${AURA_BASE}/AME_EXPORT_PACKAGE/hooks"
CONFIG_DIR="${AURA_BASE}/AME_EXPORT_PACKAGE/config"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   AURA AME AGENT - INSTALADOR UNIFICADO v2.0     ║${NC}"
echo -e "${CYAN}║   Rutas: /data/data/com.termux/files/home/...    ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── FASE 1: Dependencias del sistema ────────────────────────────────────────
echo -e "${BOLD}[1/6] Actualizando repositorios...${NC}"
pkg update -y 2>/dev/null || true
pkg upgrade -y 2>/dev/null || true

echo -e "${BOLD}[2/6] Instalando dependencias del sistema...${NC}"
pkg install -y python git openssh curl wget termux-api 2>/dev/null || true

# ─── FASE 2: Dependencias Python ─────────────────────────────────────────────
echo -e "${BOLD}[3/6] Instalando dependencias Python...${NC}"
pip install --upgrade pip 2>/dev/null || true
pip install requests websockets --break-system-packages -q 2>/dev/null || \
pip install requests websockets -q 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} requests, websockets instalados"

# ─── FASE 3: Crear estructura de directorios ──────────────────────────────────
echo -e "${BOLD}[4/6] Creando estructura de directorios...${NC}"
mkdir -p "${AME_DIR}/modules"
mkdir -p "${AME_DIR}/logs"
mkdir -p "${AME_DIR}/data"
mkdir -p "${AME_DIR}/.pids"
echo -e "  ${GREEN}✓${NC} Directorio base: ${AME_DIR}"

# ─── FASE 4: Copiar módulos consolidados ─────────────────────────────────────
echo -e "${BOLD}[5/6] Desplegando módulos...${NC}"
if [ -d "${MODULES_DIR}" ]; then
    cp "${MODULES_DIR}/osint_username.py" "${AME_DIR}/modules/"
    cp "${MODULES_DIR}/osint_reputation.py" "${AME_DIR}/modules/"
    cp "${MODULES_DIR}/wifi_client_telemetry.py" "${AME_DIR}/modules/"
    echo -e "  ${GREEN}✓${NC} osint_username.py"
    echo -e "  ${GREEN}✓${NC} osint_reputation.py"
    echo -e "  ${GREEN}✓${NC} wifi_client_telemetry.py"
else
    echo -e "  ${RED}✗${NC} Directorio de módulos no encontrado: ${MODULES_DIR}"
    echo -e "  ${YELLOW}  Asegurate de que AME_EXPORT_PACKAGE/modules/ existe${NC}"
fi

# Copiar configuración si no existe
if [ ! -f "${AME_DIR}/config.json" ] && [ -d "${CONFIG_DIR}" ]; then
    cp "${CONFIG_DIR}/ame_config_template.json" "${AME_DIR}/config.json"
    echo -e "  ${GREEN}✓${NC} config.json creado (edita con tu IP de PC)"
else
    echo -e "  ${YELLOW}ℹ${NC} config.json ya existe, conservando"
fi

# ─── FASE 5: Instalar hooks y servicios ──────────────────────────────────────
echo -e "${BOLD}[6/6] Configurando servicios...${NC}"
if [ -d "${HOOKS_DIR}" ]; then
    bash "${HOOKS_DIR}/termux_hooks.sh" install
else
    echo -e "  ${YELLOW}⚠${NC} Hooks no encontrados, configuración manual"
fi

# ─── Crear comando global 'ame' ──────────────────────────────────────────────
cat > "${AURA_BASE}/../usr/bin/ame" << 'AMECMD'
#!/data/data/com.termux/files/usr/bin/python
import sys
import os

AME_DIR = os.path.expanduser("~/AME-termux")
sys.path.insert(0, os.path.join(AME_DIR, "modules"))

modules = {
    "osint-user": ("osint_username", "check_platforms"),
    "osint-rep": ("osint_reputation", "check_ip_reputation"),
    "telemetry": ("wifi_client_telemetry", "start_standalone"),
}

if len(sys.argv) < 2:
    print("ame - Agente AME Móvil")
    print("Uso: ame <comando> [args]")
    print()
    print("Comandos:")
    print("  osint-user <usuario>    Rastreo de alias OSINT")
    print("  osint-rep <ip|dominio>  Análisis de reputación")
    print("  telemetry               Estado del nodo")
    print("  telemetry-daemon        Iniciar telemetría continua")
    print("  scan                    Escaneo de red local")
    print("  status                  Estado del sistema")
    sys.exit(0)

cmd = sys.argv[1]
args = sys.argv[2:]

if cmd == "osint-user" and args:
    mod = __import__("osint_username")
    report = mod.build_report(args[0], mod.check_platforms(args[0]))
    print(mod.format_for_discord(report))

elif cmd == "osint-rep" and args:
    mod = __import__("osint_reputation")
    target = args[0]
    if target.replace(".", "").replace(":", "").isdigit():
        print(mod.format_ip_report(mod.check_ip_reputation(target)))
    else:
        import json
        print(json.dumps(mod.check_domain_reputation(target), indent=2))

elif cmd == "telemetry":
    mod = __import__("wifi_client_telemetry")
    mod.start_standalone()

elif cmd == "telemetry-daemon":
    import asyncio
    mod = __import__("wifi_client_telemetry")
    config = mod.load_config()
    asyncio.run(mod.start_telemetry_loop(config))

elif cmd == "scan":
    mod = __import__("wifi_client_telemetry")
    import json
    print(json.dumps(mod.scan_local_network(), indent=2))

elif cmd == "status":
    import subprocess
    for svc in ["telemetry", "watchdog"]:
        pid_file = os.path.expanduser(f"~/AME-termux/.pids/{svc}.pid")
        if os.path.exists(pid_file):
            pid = open(pid_file).read().strip()
            alive = subprocess.run(["kill", "-0", pid], capture_output=True).returncode == 0
            state = "● activo" if alive else "● muerto"
            print(f"  {svc}: {state} (PID: {pid})")
        else:
            print(f"  {svc}: ○ no iniciado")

else:
    print(f"Comando desconocido: {cmd}")
    print("Ejecuta 'ame' sin argumentos para ver ayuda")
AMECMD

chmod +x "${AURA_BASE}/../usr/bin/ame" 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Comando global 'ame' instalado"

# ─── Resumen ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  INSTALACIÓN COMPLETADA${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Ubicación:${NC}  ${AME_DIR}"
echo -e "  ${BOLD}Módulos:${NC}    ${AME_DIR}/modules/"
echo -e "  ${BOLD}Config:${NC}     ${AME_DIR}/config.json"
echo ""
echo -e "  ${BOLD}Próximos pasos:${NC}"
echo -e "  1. Editar config.json con la IP de tu PC:"
echo -e "     ${YELLOW}nano ~/AME-termux/config.json${NC}"
echo ""
echo -e "  2. Activar aliases:"
echo -e "     ${YELLOW}source ~/.bash_aliases${NC}"
echo ""
echo -e "  3. Usar el agente:"
echo -e "     ${GREEN}ame osint-user target123${NC}"
echo -e "     ${GREEN}ame osint-rep 8.8.8.8${NC}"
echo -e "     ${GREEN}ame telemetry${NC}"
echo -e "     ${GREEN}ame scan${NC}"
echo ""
echo -e "  4. Iniciar daemon en background:"
echo -e "     ${GREEN}aura-start${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"