#!/bin/bash
#
# node_heartbeat.sh - Script de control Bash-Driven para nodos móviles (Termux)
# Implementa comunicación resiliente usando SSH crudo y bucles estructurados
# Sin dependencias externas (node/npm) para máxima compatibilidad con Termux
#

# Configuración global
LOG_FILE="/sdcard/aura_node_heartbeat.log"
DB_FILE="/sdcard/aura_tasks.db"
NODE_ID="$(hostname -s)_$(date +%s | tail -c 4)"
HEARTBEAT_INTERVAL=30
TASK_CHECK_INTERVAL=60
MAX_RETRIES=3
SSH_TIMEOUT=15
SSH_PORT=8022
SSH_USER="aura_user"
CONTROL_SERVER="192.168.1.100"  # Cambiar por la IP real del servidor de control

# Funciones de logging
log() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

log_error() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] ERROR: $1" | tee -a "$LOG_FILE"
}

# Verificar si SQLite está disponible
check_sqlite() {
    if ! command -v sqlite3 &> /dev/null; then
        log_error "SQLite no está instalado. Instalando..."
        pkg install sqlite -y &>> "$LOG_FILE" || {
            log_error "No se pudo instalar SQLite"
            return 1
        }
    fi
    return 0
}

# Inicializar la base de datos local
init_local_db() {
    local db="$1"

    # Crear tabla de nodos locales
    sqlite3 "$db" <<EOF
CREATE TABLE IF NOT EXISTS local_nodes (
    node_id TEXT PRIMARY KEY,
    last_heartbeat TEXT,
    status TEXT DEFAULT 'online',
    capabilities TEXT,
    pending_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_history (
    task_id TEXT PRIMARY KEY,
    node_id TEXT,
    status TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS node_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT,
    command_type TEXT,
    parameters TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    executed_at TEXT,
    result TEXT,
    error TEXT,
    retries INTEGER DEFAULT 0
);
EOF

    # Registrar este nodo localmente
    sqlite3 "$db" <<EOF
INSERT OR REPLACE INTO local_nodes (node_id, last_heartbeat, status, capabilities)
VALUES ('$NODE_ID', datetime('now'), 'online', '["osint_tools", "module_execution", "network_analysis"]');
EOF

    log "Base de datos local inicializada en $db"
}

# Registrar heartbeat en el servidor central
register_heartbeat() {
    local db="$1"
    local server="$2"
    local port="$3"
    local user="$4"

    # Obtener capacidades del nodo
    local capabilities=$(sqlite3 "$db" "SELECT capabilities FROM local_nodes WHERE node_id='$NODE_ID'")

    # Construir comando SSH con timeout
    local ssh_cmd="timeout $SSH_TIMEOUT ssh -p $port $user@$server"

    # Verificar conexión al servidor
    if ! $ssh_cmd "echo 'PING'" &> /dev/null; then
        log_error "No se pudo conectar al servidor de control: $server"
        return 1
    fi

    # Ejecutar comando de heartbeat en el servidor
    local response=$($ssh_cmd <<EOF
python3 -c "
import sys
import sqlite3
import json
from datetime import datetime

db_path = 'aura_tasks.db'
node_id = '$NODE_ID'
capabilities = $capabilities

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Actualizar heartbeat del nodo
    cursor.execute('''
        INSERT OR REPLACE INTO nodes (node_id, capabilities, last_heartbeat, status)
        VALUES (?, ?, datetime('now'), 'online')
    ''', (node_id, capabilities))

    # Obtener tareas pendientes para este nodo
    cursor.execute('''
        SELECT id, task_type, parameters, priority
        FROM tasks
        WHERE status = 'pending'
        AND JSON_EACH.value IN (SELECT JSON_EACH.value FROM json_tree(?))
        ORDER BY priority ASC
        LIMIT 5
    ''', (capabilities,))

    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            'id': row[0],
            'type': row[1],
            'parameters': json.loads(row[2]),
            'priority': row[3]
        })

    conn.commit()
    print(json.dumps({'status': 'success', 'tasks': tasks}))
except Exception as e:
    print(json.dumps({'status': 'error', 'message': str(e)}))
"
EOF)

    # Procesar respuesta
    if [[ "$response" == *"error"* ]]; then
        log_error "Error en heartbeat: $response"
        return 1
    fi

    # Parsear tareas asignadas
    local tasks=$(echo "$response" | jq -r '.tasks[]')

    if [[ -n "$tasks" ]]; then
        # Procesar cada tarea asignada
        echo "$tasks" | while read -r task; do
            local task_id=$(echo "$task" | jq -r '.id')
            local task_type=$(echo "$task" | jq -r '.type')
            local parameters=$(echo "$task" | jq -r '.parameters | tostring')

            # Registrar la tarea en la cola local
            sqlite3 "$db" <<EOF
INSERT INTO node_commands (node_id, command_type, parameters, status, created_at)
VALUES ('$NODE_ID', '$task_type', '$parameters', 'pending', datetime('now'));
EOF

            log "Tarea asignada: $task_id ($task_type)"
        done
    fi

    return 0
}

# Ejecutar comando en el nodo local
execute_local_command() {
    local db="$1"
    local command_id="$2"
    local command_type="$3"
    local parameters="$4"

    # Ejecutar el comando según el tipo
    case "$command_type" in
        "OSINT_SCAN")
            log "Ejecutando OSINT_SCAN con parámetros: $parameters"
            # Ejemplo de ejecución (simulada)
            local result=$(python3 <<EOF
import json
import time
import random

def osint_scan(target, tools, depth, timeout):
    # Simular resultados
    result = {
        "domains": [target],
        "subdomains": [f"sub1.{target}", f"api.{target}"],
        "ports": [
            {"port": 80, "service": "HTTP", "status": "open"},
            {"port": 443, "service": "HTTPS", "status": "open"}
        ],
        "vulnerabilities": [
            {"type": "potential_xss", "severity": "medium", "description": "Posible XSS en /login"}
        ]
    }
    return json.dumps(result)

# Parsear parámetros
params = json.loads('$parameters')
result = osint_scan(**params)
print(result)
EOF)

            # Guardar resultado
            sqlite3 "$db" <<EOF
UPDATE node_commands
SET status = 'completed', executed_at = datetime('now'), result = '$result'
WHERE id = $command_id;
EOF

            # Enviar resultado al servidor
            send_task_result "$db" "$command_id" "$result"
            ;;
        "OSINT_SHODAN")
            log "Ejecutando OSINT_SHODAN con parámetros: $parameters"
            # Ejecutar el módulo Venice Shodan Scanner
            local result=$(python3 /data/data/com.termux/files/home/.aura/venice_shodan_scanner.py \
                --target "$(echo "$parameters" | jq -r '.target')" \
                --mode "$(echo "$parameters" | jq -r '.mode')" \
                --output json 2>&1)

            # Guardar resultado
            sqlite3 "$db" <<EOF
UPDATE node_commands
SET status = 'completed', executed_at = datetime('now'), result = '$result'
WHERE id = $command_id;
EOF

            # Enviar resultado al servidor
            send_task_result "$db" "$command_id" "$result"
            ;;
        *)
            log_error "Tipo de comando no soportado: $command_type"
            sqlite3 "$db" <<EOF
UPDATE node_commands
SET status = 'failed', error = 'Tipo de comando no soportado', executed_at = datetime('now')
WHERE id = $command_id;
EOF
            ;;
    esac
}

# Enviar resultado de tarea al servidor
send_task_result() {
    local db="$1"
    local command_id="$2"
    local result="$3"

    # Obtener información de la tarea
    local task_info=$(sqlite3 "$db" "SELECT node_id, command_type, parameters FROM node_commands WHERE id=$command_id")

    if [[ -z "$task_info" ]]; then
        log_error "No se encontró información de la tarea con ID $command_id"
        return 1
    fi

    local node_id=$(echo "$task_info" | awk '{print $1}')
    local command_type=$(echo "$task_info" | awk '{print $2}')
    local parameters=$(echo "$task_info" | awk '{print $3}')

    # Construir comando SSH
    local ssh_cmd="timeout $SSH_TIMEOUT ssh -p $SSH_PORT $SSH_USER@$CONTROL_SERVER"

    # Ejecutar comando en el servidor
    $ssh_cmd <<EOF
python3 -c "
import sys
import sqlite3
import json

db_path = 'aura_tasks.db'
task_id = '$command_id'
result = '$result'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Obtener la tarea original
    cursor.execute('SELECT id, task_type, parameters FROM tasks WHERE id=?', (task_id,))
    row = cursor.fetchone()

    if row:
        task_type = row[1]
        params = json.loads(row[2])

        # Actualizar estado de la tarea en el servidor
        cursor.execute('''
            UPDATE tasks
            SET status = 'completed', result = ?, completed_at = datetime('now')
            WHERE id = ?
        ''', (result, task_id))

        # Crear evento de completado
        cursor.execute('''
            INSERT INTO events (id, event_type, payload, created_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (
            f'event_{task_id}_completed',
            'task_completed',
            json.dumps({
                'task_id': task_id,
                'node_id': '$node_id',
                'type': task_type,
                'result': result,
                'parameters': params
            })
        ))

        conn.commit()
        print('success')
    else:
        print('error: task_not_found')
except Exception as e:
    print(f'error: {str(e)}')
"
EOF

    # Verificar resultado
    if [[ $? -ne 0 ]]; then
        log_error "Error al enviar resultado de tarea $command_id al servidor"
    else
        log "Resultado de tarea $command_id enviado al servidor"
    fi
}

# Procesar comandos pendientes
process_pending_commands() {
    local db="$1"

    # Obtener comandos pendientes
    local commands=$(sqlite3 "$db" <<EOF
SELECT id, command_type, parameters FROM node_commands
WHERE status = 'pending' AND retries < $MAX_RETRIES
ORDER BY created_at ASC
LIMIT 5;
EOF)

    if [[ -z "$commands" ]]; then
        log "No hay comandos pendientes para procesar"
        return 0
    fi

    # Procesar cada comando
    echo "$commands" | while read -r command; do
        local command_id=$(echo "$command" | awk '{print $1}')
        local command_type=$(echo "$command" | awk '{print $2}')
        local parameters=$(echo "$command" | awk '{print $3}')

        log "Procesando comando $command_id: $command_type"

        # Ejecutar el comando localmente
        execute_local_command "$db" "$command_id" "$command_type" "$parameters"

        # Verificar si el comando falló
        local status=$(sqlite3 "$db" "SELECT status FROM node_commands WHERE id=$command_id")

        if [[ "$status" == "failed" ]]; then
            # Incrementar contador de reintentos
            sqlite3 "$db" <<EOF
UPDATE node_commands
SET retries = retries + 1
WHERE id = $command_id;
EOF

            log_error "Comando $command_id falló. Reintentos: $(sqlite3 "$db" "SELECT retries FROM node_commands WHERE id=$command_id")"
        fi
    done
}

# Verificar conexión SSH al servidor
check_ssh_connection() {
    local server="$1"
    local port="$2"
    local user="$3"

    if ! timeout $SSH_TIMEOUT ssh -p $port $user@$server "echo 'PING'" &> /dev/null; then
        log_error "Conexión SSH fallida al servidor $server:$port"
        return 1
    fi
    return 0
}

# Bucle principal de heartbeat
main_loop() {
    local db="$1"

    while true; do
        # Registrar heartbeat
        register_heartbeat "$db" "$CONTROL_SERVER" "$SSH_PORT" "$SSH_USER" || {
            log_error "Error en heartbeat. Esperando $HEARTBEAT_INTERVAL segundos..."
            sleep $HEARTBEAT_INTERVAL
            continue
        }

        # Procesar comandos pendientes
        process_pending_commands "$db"

        # Verificar conexión periódicamente
        check_ssh_connection "$CONTROL_SERVER" "$SSH_PORT" "$SSH_USER" || {
            log_error "Conexión SSH inestable. Reintentando en $TASK_CHECK_INTERVAL segundos..."
            sleep $TASK_CHECK_INTERVAL
            continue
        }

        # Esperar antes de la próxima iteración
        sleep $TASK_CHECK_INTERVAL
    done
}

# Función principal
main() {
    # Verificar dependencias
    if ! check_sqlite; then
        exit 1
    fi

    # Inicializar base de datos local
    init_local_db "$DB_FILE"

    # Verificar conexión inicial al servidor
    if ! check_ssh_connection "$CONTROL_SERVER" "$SSH_PORT" "$SSH_USER"; then
        log_error "No se puede conectar al servidor de control. Ejecutando en modo local solo."
        log "Iniciando bucle de procesamiento local..."
        while true; do
            process_pending_commands "$DB_FILE"
            sleep $TASK_CHECK_INTERVAL
        done
    fi

    # Iniciar bucle principal
    log "Iniciando bucle de heartbeat para nodo $NODE_ID"
    main_loop "$DB_FILE"
}

# Ejecutar script
main "$@"