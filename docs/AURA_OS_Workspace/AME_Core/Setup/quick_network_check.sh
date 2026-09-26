#!/bin/bash
# ──────────────────────────────────────────────
# quick_network_check.sh — Diagnóstico Rápido de Red
# Uso: bash quick_network_check.sh [SERVER_IP] [TUNNEL_DOMAIN]
# Ejemplo: bash quick_network_check.sh 192.168.1.100 aura-tunnel.midominio.com
# ──────────────────────────────────────────────

SERVER_IP="${1:-127.0.0.1}"
TUNNEL_DOMAIN="${2:-}"
AURA_PORT=5000
WS_PORT=3000
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}   AURA NETWORK DIAGNOSTIC TOOL v1.0   ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo ""
echo "Server IP: $SERVER_IP"
echo "AURA Port: $AURA_PORT"
echo "WS Port:   $WS_PORT"
echo "Tunnel:    ${TUNNEL_DOMAIN:-No configurado}"
echo ""

# ── Test 1: Conexión local al servidor Flask ──
echo -ne "[1] Flask Server ($SERVER_IP:$AURA_PORT) ... "
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://$SERVER_IP:$AURA_PORT/api/status 2>/dev/null)
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}OK (HTTP $RESPONSE)${NC}"
else
    echo -e "${RED}FALLÓ (HTTP $RESPONSE)${NC}"
    echo "  → ¿El servidor AME está corriendo? Ejecuta: python AME_Core/servidor_ame.py"
fi

# ── Test 2: Conexión local al WebSocket ──
echo -ne "[2] WebSocket Server ($SERVER_IP:$WS_PORT) ... "
WS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://$SERVER_IP:$WS_PORT/health 2>/dev/null)
if [ "$WS_RESPONSE" = "200" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}No responde en HTTP (normal si es solo WS)${NC}"
    # Intentar conexión WebSocket con python
    python3 -c "
import asyncio, websockets
async def test():
    try:
        async with websockets.connect('ws://$SERVER_IP:$WS_PORT') as ws:
            print('${GREEN}WS conectado${NC}')
    except Exception as e:
        print('${YELLOW}WS no disponible: ' + str(e).split('(')[0] + '${NC}')
asyncio.run(test())
" 2>/dev/null || echo -e "${YELLOW}  → WebSocket no alcanzable o no iniciado${NC}"
fi

# ── Test 3: Túnel Cloudflare (si configurado) ──
if [ -n "$TUNNEL_DOMAIN" ]; then
    echo -ne "[3] Cloudflare Tunnel ($TUNNEL_DOMAIN) ... "
    TUNNEL_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 https://$TUNNEL_DOMAIN/api/status 2>/dev/null)
    if [ "$TUNNEL_RESPONSE" = "200" ]; then
        echo -e "${GREEN}OK (HTTP $TUNNEL_RESPONSE)${NC}"
    else
        echo -e "${RED}FALLÓ (HTTP $TUNNEL_RESPONSE)${NC}"
        echo "  → Verifica:"
        echo "    1. cloudflared tunnel list"
        echo "    2. cloudflared tunnel info aura-tunnel"
        echo "    3. El dominio apunte al túnel en Cloudflare Dashboard"
    fi
else
    echo -ne "[3] Cloudflare Tunnel ... ${YELLOW}SALTADO (sin dominio)${NC}"
    echo ""
fi

# ── Test 4: Resolución DNS ──
echo -ne "[4] Resolución DNS ... "
DNS_OK=true
for host in "$SERVER_IP" "localhost" "api.aura-system.com"; do
    if [[ "$host" =~ ^[0-9]+\.[0-9]+ ]]; then
        echo -ne " $host(IP)✓"
    else
        nslookup "$host" >/dev/null 2>&1 && echo -ne " $host✓" || { echo -ne " $host${RED}✗${NC}"; DNS_OK=false; }
    fi
done
echo ""
if [ "$DNS_OK" = true ]; then
    echo -e "${GREEN}  → DNS OK${NC}"
else
    echo -e "${RED}  → Algunos DNS fallaron${NC}"
fi

# ── Test 5: Ping al servidor ──
echo -ne "[5] Ping al servidor ($SERVER_IP) ... "
if ping -c 1 -W 3 "$SERVER_IP" >/dev/null 2>&1; then
    RTT=$(ping -c 1 -W 3 "$SERVER_IP" 2>/dev/null | grep -oP 'time=\K[0-9.]+' || echo "0")
    echo -e "${GREEN}OK (${RTT}ms)${NC}"
else
    echo -e "${RED}FALLÓ (timeout)${NC}"
    echo "  → El servidor $SERVER_IP no responde a ping"
fi

# ── Test 6: Puertos abiertos ──
echo -ne "[6] Puertos abiertos ... "
PORTS=($AURA_PORT $WS_PORT)
ALL_OPEN=true
for port in "${PORTS[@]}"; do
    timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/$port" 2>/dev/null && \
        echo -ne " :$port${GREEN}✓${NC}" || \
        { echo -ne " :$port${RED}✗${NC}"; ALL_OPEN=false; }
done
echo ""
if [ "$ALL_OPEN" = true ]; then
    echo -e "${GREEN}  → Todos los puertos accesibles${NC}"
else
    echo -e "${RED}  → Algunos puertos no accesibles${NC}"
    echo "  → Verifica firewall: firewall-cmd --list-ports o iptables -L"
fi

# ── Resumen ──
echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}   RESUMEN DE DIAGNÓSTICO${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo ""
echo "Archivos de configuración:"
echo "  config.json         → $([[ -f AURA_Core/config.json ]] && echo '✓' || echo '✗')"
echo "  proxy_manager.py    → $([[ -f AME_Core/proxy_manager.py ]] && echo '✓' || echo '✗')"
echo "  servidor_ame.py     → $([[ -f AME_Core/servidor_ame.py ]] && echo '✓' || echo '✗')"
echo "  cloudflared/config.yml → $([[ -f cloudflared/config.yml ]] && echo '✓' || echo '✗')"
echo ""
echo "Comandos útiles:"
echo "  Iniciar servidor:  python AME_Core/servidor_ame.py"
echo "  Ver logs túnel:    cloudflared tunnel info aura-tunnel --metrics"
echo "  Logs Android:      adb logcat | grep -i failed"
echo "  WebSocket test:    python -c \"import websockets; import asyncio; asyncio.run(websockets.connect('ws://$SERVER_IP:$WS_PORT'))\""
echo ""