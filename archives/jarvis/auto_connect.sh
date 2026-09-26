#!/data/data/com.termux/files/usr/bin/bash

# Configuración
PC_IP="192.168.3.10"
PC_USER="u0_a1167"
PC_PORT="8022"
PC_PASSWORD="termux123"
PING_INTERVAL=30
SSH_SERVICE="sshd:openssh"
NOTIFICATION_CMD="termux-notification"

# Función para mostrar notificación
show_notification() {
    local title="$1"
    local message="$2"
    $NOTIFICATION_CMD -c "AURA" -t "$title" -m "$message"
}

# Función para verificar si la PC está disponible
check_pc_available() {
    ping -c 1 -W 2 "$PC_IP" &> /dev/null
    return $?
}

# Función para iniciar servicios
start_services() {
    # Iniciar SSH
    if ! pgrep -x "$SSH_SERVICE" > /dev/null; then
        sshd &> /dev/null &
        sleep 2
    fi

    # Activar wake lock
    termux-wake-lock &
}

# Función para detener servicios
stop_services() {
    # Detener SSH
    pkill -f "$SSH_SERVICE" &> /dev/null

    # Liberar wake lock
    termux-wake-unlock &> /dev/null
}

# Bucle principal
while true; do
    if check_pc_available; then
        # Verificar si SSH ya está corriendo
        if ! pgrep -x "$SSH_SERVICE" > /dev/null; then
            start_services
            show_notification "PC Detectada" "SSH activado y wake lock activado"
        fi
    else
        # Verificar si SSH está corriendo y detenerlo
        if pgrep -x "$SSH_SERVICE" > /dev/null; then
            stop_services
            show_notification "PC Desconectada" "SSH detenido y wake lock liberado"
        fi
    fi

    sleep $PING_INTERVAL
done