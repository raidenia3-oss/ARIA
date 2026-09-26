#!/bin/bash
"""
enter_standby.sh - Script para poner el sistema en modo Standby.
Este script se ejecuta cuando el gatekeeper detecta condiciones de seguridad no cumplidas.
Realiza acciones para proteger la integridad del nodo y notificar al sistema.
"""

# Configuración
LOG_FILE="/data/data/com.termux/files/home/standby.log"
NODE_ID="mobile_node_001"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
STANDBY_MODE="security_standby"
LOG_LEVEL="WARNING"

# Función para registrar logs
log_message() {
    local level=$1
    local message=$2
    echo "[$TIMESTAMP] [$level] [$NODE_ID] $message" | tee -a "$LOG_FILE"
}

# Función para notificar al servidor AURA
notify_aura() {
    local message=$1
    local details=$2

    # Intentar enviar notificación vía curl (si está disponible)
    if command -v curl &> /dev/null; then
        log_message "INFO" "Intentando notificar a AURA: $message"

        # Usar el token de autenticación del gatekeeper
        local aura_token="aura_gatekeeper_token_123"
        local aura_url="http://localhost:3000/api/alerts"

        # Crear payload JSON
        local payload=$(jq -n \
            --arg msg "$message" \
            --argjson ts "$(date +%s000)" \
            --arg node "$NODE_ID" \
            --arg type "system_standby" \
            --argjson severity 1 \
            --argjson src 1 \
            --arg details "$details" \
            '{
                timestamp: ($ts | todateiso8601),
                node_id: $node,
                alert_type: $type,
                severity: "critical",
                message: $msg,
                details: $details,
                source: "standby_script"
            }')

        # Enviar la notificación
        if curl -s -X POST "$aura_url" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $aura_token" \
            -d "$payload" > /dev/null 2>&1; then
            log_message "INFO" "Notificación enviada a AURA con éxito"
        else
            log_message "ERROR" "Error al enviar notificación a AURA"
        fi
    else
        log_message "WARNING" "curl no disponible. No se pudo notificar a AURA"
    fi
}

# Función para detener módulos en ejecución
stop_modules() {
    log_message "INFO" "Deteniendo módulos en ejecución..."

    # Buscar y matar procesos de Python relacionados con AURA
    pkill -f "python.*\.aura" > /dev/null 2>&1
    pkill -f "python.*venice" > /dev/null 2>&1
    pkill -f "python.*module" > /dev/null 2>&1

    # Verificar si se detuvo algún proceso
    if pgrep -f "python.*\.aura" > /dev/null || pgrep -f "python.*venice" > /dev/null || pgrep -f "python.*module" > /dev/null; then
        log_message "WARNING" "Algunos módulos podrían seguir en ejecución"
    else
        log_message "INFO" "Módulos detenidos con éxito"
    fi
}

# Función para deshabilitar interfaces de red no esenciales
disable_network() {
    log_message "INFO" "Deshabilitando interfaces de red no esenciales..."

    # Deshabilitar interfaces que no sean lo o wlan0 (si están activas)
    for iface in $(ip link show | awk -F': ' '/^[2-9]: / {print $2}'); do
        if [[ "$iface" != "lo" && "$iface" != "wlan0" ]]; then
            if ip link show "$iface" | grep -q "state UP"; then
                ip link set "$iface" down > /dev/null 2>&1
                log_message "INFO" "Interface $iface deshabilitada"
            fi
        fi
    done
}

# Función para reducir el uso de recursos
reduce_resources() {
    log_message "INFO" "Reduciendo uso de recursos..."

    # Reducir brillo de pantalla (si es posible)
    if command -v termux-set-brightness &> /dev/null; then
        termux-set-brightness 0.1 > /dev/null 2>&1
        log_message "INFO" "Brillo de pantalla reducido"
    fi

    # Limitar frecuencia de CPU (si es posible)
    if command -v cpufreq-set &> /dev/null; then
        cpufreq-set -g powersave > /dev/null 2>&1
        log_message "INFO" "Frecuencia de CPU limitada a modo powersave"
    fi
}

# Función principal de standby
enter_standby() {
    log_message "INFO" "Entrando en modo Standby debido a condiciones de seguridad no cumplidas"

    # Crear registro detallado del evento
    local details=$(jq -n \
        --arg node "$NODE_ID" \
        --arg ts "$TIMESTAMP" \
        --arg mode "$STANDBY_MODE" \
        '{
            node_id: $node,
            timestamp: $ts,
            mode: $mode,
            reason: "Condiciones de seguridad no cumplidas",
            actions_taken: []
        }')

    # Notificar a AURA
    notify_aura "Modo Standby activado en $NODE_ID" "$details"

    # Ejecutar acciones de standby
    stop_modules
    disable_network
    reduce_resources

    # Actualizar detalles con las acciones realizadas
    local actions=(
        "stop_modules"
        "disable_network"
        "reduce_resources"
    )

    for action in "${actions[@]}"; do
        details=$(echo "$details" | jq --arg action "$action" '.actions_taken += [$action]')
    done

    # Registrar detalles finales en el log
    log_message "INFO" "Modo Standby activado con éxito"
    echo "Detalles del evento:" | tee -a "$LOG_FILE"
    echo "$details" | jq '.' | tee -a "$LOG_FILE"

    # Notificar al usuario
    echo "🛑 ALERTA: Modo Standby activado" | tee -a "$LOG_FILE"
    echo "   Razón: Condiciones de seguridad no cumplidas" | tee -a "$LOG_FILE"
    echo "   Acciones realizadas:" | tee -a "$LOG_FILE"
    for action in "${actions[@]}"; do
        echo "   - $action" | tee -a "$LOG_FILE"
    done
    echo "   El nodo está protegido y en modo seguro." | tee -a "$LOG_FILE"

    # Esperar un tiempo antes de salir (para permitir que el sistema se estabilice)
    sleep 30
}

# Iniciar el modo standby
enter_standby

exit 0