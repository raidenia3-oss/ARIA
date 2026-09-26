#!/data/data/com.termux/files/usr/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# termux_hooks.sh - Ganchos nativos de ejecución para AME en Termux
# Rutas absolutas: /data/data/com.termux/files/home/...
# Ejecutar: bash termux_hooks.sh [start|stop|status|install|uninstall]
# ══════════════════════════════════════════════════════════════════════════════

AURA_BASE="/data/data/com.termux/files/home"
AME_DIR="${AURA_BASE}/AME-termux"
MODULES_DIR="${AURA_BASE}/AME_EXPORT_PACKAGE/modules"
LOG_DIR="${AME_DIR}/logs"
PID_DIR="${AME_DIR}/.pids"
LOCKFILE="${AURA_BASE}/.ame_lock"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[AURA]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }

# ─── Instalación ─────────────────────────────────────────────────────────────
install() {
    log "Instalando hooks de AURA en Termux..."

    # Crear directorios necesarios
    mkdir -p "${LOG_DIR}" "${PID_DIR}"
    mkdir -p "${AME_DIR}/modules"
    mkdir -p "${AME_DIR}/data"

    # Copiar módulos si existen en el paquete exportado
    if [ -d "${MODULES_DIR}" ]; then
        cp -v "${MODULES_DIR}"/*.py "${AME_DIR}/modules/" 2>/dev/null
        ok "Módulos copiados a ${AME_DIR}/modules/"
    else
        warn "Directorio de módulos no encontrado: ${MODULES_DIR}"
    fi

    # Instalar servicio termux-api si no está
    if ! command -v termux-wifi-connectioninfo &> /dev/null; then
        log "Instalando termux-api..."
        pkg install -y termux-api 2>/dev/null
    fi

    # Crear alias útiles
    ALIAS_FILE="${AURA_BASE}/.bash_aliases"
    cat > "${ALIAS_FILE}" << 'ALIASES'
# ─── AURA Aliases ────────────────────────────────────────────────────────────
alias aura-start='bash /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/hooks/termux_hooks.sh start'
alias aura-stop='bash /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/hooks/termux_hooks.sh stop'
alias aura-status='bash /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/hooks/termux_hooks.sh status'
alias aura-telemetry='python /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/modules/wifi_client_telemetry.py'
alias aura-osint-user='python /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/modules/osint_username.py'
alias aura-osint-rep='python /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/modules/osint_reputation.py'
alias aura-logs='tail -f /data/data/com.termux/files/home/AME-termux/logs/aura.log'
# ─────────────────────────────────────────────────────────────────────────────
ALIASES
    ok "Aliases creados en ${ALIAS_FILE}"

    # Crear servicio Termux:Boot
    BOOT_DIR="${AURA_BASE}/.termux/boot"
    mkdir -p "${BOOT_DIR}"
    cat > "${BOOT_DIR}/start-aura.sh" << 'BOOTSCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
bash /data/data/com.termux/files/home/AME_EXPORT_PACKAGE/hooks/termux_hooks.sh start
BOOTSCRIPT
    chmod +x "${BOOT_DIR}/start-aura.sh"
    ok "Servicio de auto-inicio configurado en .termux/boot/"

    ok "Instalación completada. Ejecuta 'source ${ALIAS_FILE}' para activar aliases."
}

# ─── Iniciar daemon ───────────────────────────────────────────────────────────
start() {
    log "Iniciando daemon AURA..."

    # Verificar si ya está corriendo
    if [ -f "${LOCKFILE}" ]; then
        OLD_PID=$(cat "${LOCKFILE}")
        if kill -0 "${OLD_PID}" 2>/dev/null; then
            warn "Daemon ya corriendo con PID ${OLD_PID}"
            return 1
        fi
        rm -f "${LOCKFILE}"
    fi

    # Adquirir wake-lock
    termux-wake-lock 2>/dev/null

    # Iniciar telemetría en background
    nohup python "${MODULES_DIR}/wifi_client_telemetry.py" --daemon \
        >> "${LOG_DIR}/telemetry.log" 2>&1 &
    echo $! > "${PID_DIR}/telemetry.pid"
    ok "Telemetría iniciada (PID: $!)"

    # Iniciar watchdog de procesos
    nohup bash -c '
        while true; do
            # Verificar telemetría
            TPID=$(cat '"${PID_DIR}/telemetry.pid"' 2>/dev/null)
            if [ -n "$TPID" ] && ! kill -0 "$TPID" 2>/dev/null; then
                echo "[$(date)] Telemetría caída, reiniciando..." >> '"${LOG_DIR}/watchdog.log"'
                nohup python '"${MODULES_DIR}/wifi_client_telemetry.py"' --daemon \
                    >> '"${LOG_DIR}/telemetry.log"' 2>&1 &
                echo $! > '"${PID_DIR}/telemetry.pid"'
            fi
            sleep 60
        done
    ' >> "${LOG_DIR}/watchdog.log" 2>&1 &
    echo $! > "${PID_DIR}/watchdog.pid"
    ok "Watchdog iniciado (PID: $!)"

    # Guardar PID principal
    echo $$ > "${LOCKFILE}"
    ok "Daemon AURA iniciado correctamente"
    status
}

# ─── Detener daemon ───────────────────────────────────────────────────────────
stop() {
    log "Deteniendo daemon AURA..."

    for svc in telemetry watchdog; do
        PID_FILE="${PID_DIR}/${svc}.pid"
        if [ -f "${PID_FILE}" ]; then
            PID=$(cat "${PID_FILE}")
            if kill -0 "${PID}" 2>/dev/null; then
                kill "${PID}" 2>/dev/null
                ok "${svc} detenido (PID: ${PID})"
            fi
            rm -f "${PID_FILE}"
        fi
    done

    rm -f "${LOCKFILE}"
    warn "Daemon AURA detenido"
}

# ─── Estado ───────────────────────────────────────────────────────────────────
status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  AURA NODE STATUS - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"

    for svc in telemetry watchdog; do
        PID_FILE="${PID_DIR}/${svc}.pid"
        if [ -f "${PID_FILE}" ]; then
            PID=$(cat "${PID_FILE}")
            if kill -0 "${PID}" 2>/dev/null; then
                echo -e "  ${GREEN}●${NC} ${svc}: activo (PID: ${PID})"
            else
                echo -e "  ${RED}●${NC} ${svc}: muerto"
            fi
        else
            echo -e "  ${YELLOW}●${NC} ${svc}: no iniciado"
        fi
    done

    # Info de red
    LOCAL_IP=$(python -c "import socket; s=socket.socket(); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "N/A")
    SSID=$(termux-wifi-connectioninfo 2>/dev/null | python -c "import sys,json; print(json.load(sys.stdin).get('ssid','N/A'))" 2>/dev/null || echo "N/A")
    echo ""
    echo -e "  IP: ${LOCAL_IP} | SSID: ${SSID}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
}

# ─── Desinstalar ──────────────────────────────────────────────────────────────
uninstall() {
    log "Desinstalando hooks de AURA..."
    stop
    rm -f "${AURA_BASE}/.bash_aliases"
    rm -f "${BOOT_DIR}/start-aura.sh" 2>/dev/null
    ok "Hooks desinstalados (módulos conservados en ${AME_DIR})"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
case "${1:-help}" in
    install)   install ;;
    start)     start ;;
    stop)      stop ;;
    status)    status ;;
    uninstall) uninstall ;;
    *)
        echo "Uso: $0 [install|start|stop|status|uninstall]"
        echo ""
        echo "  install   - Instala aliases, servicios y dependencias"
        echo "  start     - Inicia daemon de telemetría y watchdog"
        echo "  stop      - Detiene todos los servicios"
        echo "  status    - Muestra estado de servicios y red"
        echo "  uninstall - Detiene y remueve hooks"
        ;;
esac