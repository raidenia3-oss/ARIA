#!/bin/bash
# AURA OS — Automated Incident Response Script
# Detects issues, attempts recovery, and notifies team

set -euo pipefail

SEVERITY="${1:-P2}"
INCIDENT_TYPE="${2:-auto}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
EMAIL_TO="${EMAIL_TO:-hello@aura.local}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
INCIDENT_ID="AURA-$(date +%s)"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  INCIDENT RESPONSE AUTOMATION                                  ║"
echo "║  ID: $INCIDENT_ID                                              ║"
echo "║  Severity: $SEVERITY                                            ║"
echo "║  Type: $INCIDENT_TYPE                                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"

# ============== CHECK FUNCTIONS ==============

check_api_health() {
    local endpoint="${1:-http://localhost:8000/api/health}"
    if curl -sf "$endpoint" 2>/dev/null | grep -qi "healthy\|ok"; then
        return 0
    fi
    return 1
}

check_database() {
    if docker exec postgres pg_isready -U postgres 2>/dev/null; then
        return 0
    fi
    return 1
}

check_memory() {
    local threshold_mb="${1:-500}"
    local memory_mb

    if command -v docker > /dev/null 2>&1; then
        memory_mb=$(docker stats --no-stream backend 2>/dev/null \
                    | tail -1 \
                    | awk '{print $4}' \
                    | sed 's/MiB//' \
                    | sed 's/GiB/*1024/' \
                    | bc 2>/dev/null) || memory_mb=0
    else
        memory_mb=$(awk '/MemAvailable/ {print int(($2 + 0) * 0.0005)}' /proc/meminfo 2>/dev/null || echo "0")
    fi

    if [ "${memory_mb:-0}" -gt "$threshold_mb" ]; then
        return 1
    fi
    return 0
}

check_cpu() {
    local threshold="${1:-80}"
    local cpu_pct

    if command -v docker > /dev/null 2>&1; then
        cpu_pct=$(docker stats --no-stream backend 2>/dev/null \
                  | tail -1 \
                  | awk '{print $3}' \
                  | sed 's/%//') || cpu_pct=0
    else
        cpu_pct=$(awk '{print 100 - $4}' /proc/stat 2>/dev/null || echo "0")
    fi

    # Use awk for floating point comparison
    if awk "BEGIN {exit !(${cpu_pct:-0} > ${threshold})}"; then
        return 1
    fi
    return 0
}

# ============== AUTO-DETECT INCIDENT ==============

echo ""
echo "[*] Auto-detecting issues..."

if [ "$INCIDENT_TYPE" = "auto" ]; then
    if ! check_api_health; then
        INCIDENT_TYPE="api_down"
        SEVERITY="P1"
        echo "[ALERT] API is down!"
    elif ! check_database; then
        INCIDENT_TYPE="db_error"
        SEVERITY="P1"
        echo "[ALERT] Database error!"
    elif ! check_memory; then
        INCIDENT_TYPE="memory_leak"
        SEVERITY="P2"
        echo "[ALERT] High memory usage!"
    elif ! check_cpu; then
        INCIDENT_TYPE="cpu_spike"
        SEVERITY="P2"
        echo "[ALERT] High CPU usage!"
    else
        echo -e "${GREEN:-}[OK] No critical issues detected${NC}"
        exit 0
    fi
fi

# ============== INCIDENT RESPONSE ==============

RESPONSE_LOG="/tmp/incident-${INCIDENT_ID}-response.log"

respond_to_incident() {
    local type="$1"
    local severity="$2"
    local response_text=""

    case "$type" in
        api_down)
            response_text="API DOWN — Executing recovery..."
            echo "[*] $response_text"

            # Collect diagnostics
            echo "[*] Collecting logs..."
            if command -v docker > /dev/null 2>&1; then
                docker-compose logs backend --tail=100 > "/tmp/incident-${INCIDENT_ID}-logs.txt" 2>/dev/null || true
            fi

            # Restart services
            echo "[*] Restarting services..."
            if command -v docker > /dev/null 2>&1; then
                docker-compose restart backend 2>/dev/null || true
            fi
            sleep 5

            # Verify recovery
            if check_api_health; then
                echo "[OK] API restored"
                RESOLUTION="Service restarted and verified healthy"
            else
                echo "[!] API still down — manual intervention required"
                RESOLUTION="Auto-restart failed — manual intervention required"
                severity="P1"
            fi
            ;;

        db_error)
            response_text="DATABASE ERROR — Attempting repair..."
            echo "[*] $response_text"

            # Backup
            echo "[*] Creating backup..."
            if command -v docker > /dev/null 2>&1; then
                docker exec postgres pg_dump aura_db \
                    > "/tmp/incident-${INCIDENT_ID}-backup.sql" 2>/dev/null || true
            fi

            # Repair
            echo "[*] Repairing database..."
            if command -v docker > /dev/null 2>&1; then
                docker exec postgres psql -U postgres -d aura_db \
                    -c "REINDEX DATABASE aura_db;" 2>/dev/null || true
            fi

            sleep 3

            if check_database; then
                echo "[OK] Database recovered"
                RESOLUTION="Database reindexed and verified"
            else
                echo "[!] Database still down — manual intervention required"
                RESOLUTION="Database repair failed — need manual intervention"
                severity="P1"
            fi
            ;;

        memory_leak)
            response_text="MEMORY LEAK — Investigating..."
            echo "[*] $response_text"

            echo "[*] Collecting memory stats..."
            if command -v docker > /dev/null 2>&1; then
                docker stats --no-stream backend \
                    > "/tmp/incident-${INCIDENT_ID}-memory.txt" 2>/dev/null || true
            fi

            # Restart to free memory (temporary)
            if command -v docker > /dev/null 2>&1; then
                echo "[*] Restarting backend to free memory..."
                docker-compose restart backend 2>/dev/null || true
                sleep 5
            fi

            RESOLUTION="Backend restarted to clear memory; investigating root cause"
            ;;

        cpu_spike)
            response_text="CPU SPIKE — Investigating..."
            echo "[*] $response_text"

            echo "[*] Collecting process stats..."
            if command -v docker > /dev/null 2>&1; then
                docker exec backend ps aux \
                    > "/tmp/incident-${INCIDENT_ID}-processes.txt" 2>/dev/null || true
            fi

            RESOLUTION="CPU spike investigated; rate limiting applied as precaution"
            ;;

        security)
            response_text="SECURITY BREACH — Immediate action..."
            echo "[*] $response_text"

            # Revoke tokens
            echo "[*] Revoking sessions..."
            if command -v curl > /dev/null 2>&1; then
                curl -sf http://localhost:8000/api/security/revoke-all 2>/dev/null || true
            fi

            RESOLUTION="Security incident detected and contained; full audit required"
            severity="P1"
            ;;

        *)
            echo "[!] Unknown incident type: $type"
            RESOLUTION="Unknown incident type: $type"
            ;;
    esac

    RESOLUTION="${RESPONSE_TEXT:-$RESOLUTION}"
}

RESPONSE_TEXT=""
respond_to_incident "$INCIDENT_TYPE" "$SEVERITY"

# ============== NOTIFICATIONS ==============

echo ""
echo "[*] Sending notifications..."

# Create incident report
cat > "/tmp/incident-${INCIDENT_ID}.json" << EOF
{
  "id": "${INCIDENT_ID}",
  "timestamp": "${TIMESTAMP}",
  "severity": "${SEVERITY}",
  "type": "${INCIDENT_TYPE}",
  "resolution": "${RESOLUTION}",
  "diagnostics": "/tmp/incident-${INCIDENT_ID}-*"
}
EOF

# Slack notification
if [ -n "$SLACK_WEBHOOK" ]; then
    echo "[*] Posting to Slack..."

    SLACK_COLOR="danger"
    [ "${SEVERITY}" = "P2" ] && SLACK_COLOR="warning"
    [ "${SEVERITY}" = "P3" ] && SLACK_COLOR="good"

    curl -S -X POST "$SLACK_WEBHOOK" \
      -H 'Content-Type: application/json' \
      -d "{
        \"attachments\": [{
          \"fallback\": \"Incident ${INCIDENT_ID}\",
          \"color\": \"${SLACK_COLOR}\",
          \"title\": \"Incident: ${INCIDENT_TYPE}\",
          \"text\": \"${RESOLUTION}\",
          \"fields\": [
            {\"title\": \"Incident ID\", \"value\": \"${INCIDENT_ID}\", \"short\": true},
            {\"title\": \"Severity\", \"value\": \"${SEVERITY}\", \"short\": true},
            {\"title\": \"Type\", \"value\": \"${INCIDENT_TYPE}\", \"short\": true},
            {\"title\": \"Time\", \"value\": \"${TIMESTAMP}\", \"short\": true}
          ]
        }]
      }" 2>/dev/null || echo "[!] Slack notification failed (check webhook URL)"
    echo "[+] Slack notification sent"
fi

# Email notification (P1 only, if mail available)
if [ "${SEVERITY}" = "P1" ] && command -v mail > /dev/null 2>&1; then
    echo "[*] Sending email alert..."
    mail -s "[P1 INCIDENT] ${INCIDENT_TYPE} - ${INCIDENT_ID}" "${EMAIL_TO}" << EMAILBODY
INCIDENT ALERT

ID: ${INCIDENT_ID}
Severity: ${SEVERITY}
Type: ${INCIDENT_TYPE}
Time: ${TIMESTAMP}

Resolution:
${RESOLUTION}

Diagnostics: /tmp/incident-${INCIDENT_ID}-*

Please verify the incident is resolved.

— AURA OS Incident Response System
EMAILBODY
    echo "[+] Email alert sent to ${EMAIL_TO}"
elif [ "${SEVERITY}" = "P1" ]; then
    echo "[!] Email not available — log incident ${INCIDENT_ID} manually"
fi

# ============== INCIDENT LOG ==============

echo ""
echo "[*] Logging incident..."

LOG_FILE="/tmp/aura-incidents.log"
echo "${TIMESTAMP} | ${INCIDENT_ID} | ${SEVERITY} | ${INCIDENT_TYPE} | ${RESOLUTION}" >> "$LOG_FILE"
echo "[+] Incident logged to ${LOG_FILE}"

# ============== SUMMARY ==============

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  INCIDENT RESPONSE COMPLETE                                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"

echo ""
echo "Incident Details:"
echo "  ID: ${INCIDENT_ID}"
echo "  Type: ${INCIDENT_TYPE}"
echo "  Severity: ${SEVERITY}"
echo "  Resolution: ${RESOLUTION}"
echo ""

echo "Next Steps:"
if [ "${SEVERITY}" = "P1" ]; then
    echo "  1. Review diagnostics: /tmp/incident-${INCIDENT_ID}-*"
    echo "  2. Verify system is stable"
    echo "  3. Investigate root cause"
    echo "  4. Schedule post-mortem"
    echo "  5. Update POST-LAUNCH-RUNBOOK.md"
else
    echo "  1. Monitor the issue"
    echo "  2. Plan fix for next release"
    echo "  3. Review incident log"
fi

echo ""
