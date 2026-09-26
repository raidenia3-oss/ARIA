#!/data/data/com.termux/files/usr/bin/bash
# fetch_network_target.sh - Ultra-ligero: obtiene la IP de la PC y actualiza la config
# Uso en Termux: bash fetch_network_target.sh
# O auto-ejecutar con: termux-boot

LOG_FILE="/sdcard/aura_sync.log"
CONFIG_FILE="/sdcard/aura_config.json"
PC_URL="http://PC_IP_PLACEHOLDER:5000/aura_urls.json"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "🔄 Aura Network Sync - Iniciando..."

# 1. Obtener IP de la PC (vía cloud o directo)
CONFIG_URL="$PC_URL"
log "📡 Consultando config: $CONFIG_URL"

HTTP_CODE=$(curl -s -o "$CONFIG_FILE.tmp" -w "%{http_code}" --max-time 5 "$CONFIG_URL" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ] && [ -s "$CONFIG_FILE.tmp" ]; then
    mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    log "✅ Config actualizada desde PC"
else
    rm -f "$CONFIG_FILE.tmp"
    log "⚠️  No se pudo obtener config (HTTP $HTTP_CODE)"
    log "   Intentando ruta alternativa..."
    # Ruta alternativa: intentar IP del gateway
    GW=$(ip route | grep default | awk '{print $3}')
    if [ -n "$GW" ]; then
        ALT_URL="http://${GW}:5000/aura_urls.json"
        HTTP_CODE=$(curl -s -o "$CONFIG_FILE.tmp" -w "%{http_code}" --max-time 5 "$ALT_URL" 2>/dev/null)
        if [ "$HTTP_CODE" = "200" ] && [ -s "$CONFIG_FILE.tmp" ]; then
            mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
            log "✅ Config actualizada desde gateway: $GW"
        fi
    fi
fi

# 2. Leer IP del config
if [ -f "$CONFIG_FILE" ]; then
    SERVER_IP=$(grep -o '"server_ip":"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
    SERVER_PORT=$(grep -o '"server_port":[0-9]*' "$CONFIG_FILE" | cut -d: -f2)
    log "🎯 IP objetivo: ${SERVER_IP}:${SERVER_PORT}"
else
    log "❌ No hay archivo de config"
    exit 1
fi

# 3. TDD: Verificar conectividad
log "🔍 Verificando conexión a ${SERVER_IP}:${SERVER_PORT}..."
HTTP_CHECK=$(curl -I -s --max-time 3 "http://${SERVER_IP}:${SERVER_PORT}/health" 2>/dev/null | head -1)

if echo "$HTTP_CHECK" | grep -q "200"; then
    log "✅ Conexión verificada - Puerto ${SERVER_PORT} activo"
    STATUS="OK"
elif echo "$HTTP_CHECK" | grep -q "HTTP"; then
    log "⚠️  Servidor responde pero no es 200: $HTTP_CHECK"
    STATUS="PARTIAL"
else
    log "❌ No se pudo conectar a ${SERVER_IP}:${SERVER_PORT}"
    log "   Verifica que la PC esté encendida y en la misma red"
    STATUS="FAILED"
fi

# 4. Reporte final
log "📊 Estado: $STATUS"
log "📋 Config: $CONFIG_FILE"
log "📋 Log: $LOG_FILE"

# Guardar estado para que el APK lo lea
echo "{\"status\":\"$STATUS\",\"ip\":\"$SERVER_IP\",\"port\":\"$SERVER_PORT\",\"timestamp\":\"$(date -Iseconds)\"}" > /sdcard/aura_network_status.json

log "✅ Sincronización completada"