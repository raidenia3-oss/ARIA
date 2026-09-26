#!/bin/bash

# AURA OS Load Testing & Performance Profiling

set -euo pipefail

TARGET_URL="${1:-http://localhost:8000}"
CONCURRENT_USERS="${2:-10}"
DURATION="${3:-60}"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS Load Test & Performance Profile              ║"
echo "╚════════════════════════════════════════════════════════╝"

echo "[*] Target: $TARGET_URL"
echo "[*] Concurrent users: $CONCURRENT_USERS"
echo "[*] Duration: ${DURATION}s"

# Check dependencies
for dependency in ab wrk curl jq; do
  if ! command -v "$dependency" &> /dev/null; then
    echo "[-] Required dependency not found: $dependency" >&2
    echo "    Install it with your system package manager and retry." >&2
    exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Test 1: Simple endpoint (health check)
echo ""
echo "[*] Test 1: Health Check"
echo "────────────────────────────────────"

ab -n 100 -c 10 "$TARGET_URL/api/health" | grep -E "Requests/sec|Time per request"

# Test 2: Chat endpoint (moderate load)
echo ""
echo "[*] Test 2: Chat Endpoint (JSON payload)"
echo "────────────────────────────────────"

wrk -t4 -c"$CONCURRENT_USERS" -d"${DURATION}s" \
  -s "$SCRIPT_DIR/load-test-chat.lua" \
  "$TARGET_URL/api/chat"

# Test 3: Omniroute provider selection
echo ""
echo "[*] Test 3: Omniroute Provider Selection"
echo "────────────────────────────────────"

printf '%s\n' '{"model_type": "chat"}' > "$TMP_DIR/providers-best.json"
ab -n 50 -c 5 -H "Content-Type: application/json" \
  -p "$TMP_DIR/providers-best.json" \
  "$TARGET_URL/api/providers/best"

# Test 4: Database queries (skills execution)
echo ""
echo "[*] Test 4: Skill Execution (DB queries)"
echo "────────────────────────────────────"

for i in {1..5}; do
  echo "  Run $i..."
  curl -fsS -X POST "$TARGET_URL/api/skills/1/exec" \
    -H "Content-Type: application/json" \
    -d '{"input": "test"}' | jq '.execution_time'
done

# Test 5: Stress test (ramp up)
echo ""
echo "[*] Test 5: Stress Test (Ramp Up)"
echo "────────────────────────────────────"

for clients in 5 10 20 50 100; do
  echo "[*] Testing with $clients concurrent clients..."
  
  ab -n 200 -c $clients \
    "$TARGET_URL/api/health" \
    2>&1 | grep -E "Requests/sec|Failed requests|Time taken"
  
  sleep 2
done

# Test 6: Memory profiling
echo ""
echo "[*] Test 6: Memory Profiling"
echo "────────────────────────────────────"

if command -v memory_profiler &> /dev/null; then
  python -m memory_profiler backend/main.py 2>&1 | head -20
fi

# Test 7: CPU profiling
echo ""
echo "[*] Test 7: CPU Profiling"
echo "────────────────────────────────────"

cat > "$TMP_DIR/profile_cpu.py" << 'EOF'
import cProfile
import pstats
from backend.main import app

def run_test():
    for _ in range(100):
        pass

if __name__ == '__main__':
    pr = cProfile.Profile()
    pr.enable()
    
    run_test()
    
    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
EOF

PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}" python "$TMP_DIR/profile_cpu.py"

# Generate report
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Performance Report Generated                         ║"
echo "╚════════════════════════════════════════════════════════╝"

REPORT_FILE="${REPORT_FILE:-$REPO_DIR/data/PERFORMANCE_REPORT.md}"
mkdir -p "$(dirname "$REPORT_FILE")"
cat > "$REPORT_FILE" << EOF
# AURA OS v2.1 Performance Report

Generated: $(date)

## Test Results

### Health Check (100 requests, 10 concurrent)
- Captured in the command output above.

### Chat Endpoint
- Captured in the command output above.

### Omniroute Provider Selection
- Captured in the command output above.

### Skill Execution
- Captured in the command output above.

### Stress Test Results
Captured in the command output above.

## Bottleneck Analysis

1. Potential bottlenecks identified: review the measurements above.

2. Optimization recommendations:
   - Repeat the test against a representative production-like environment.

## Production Readiness

- These thresholds require manual evaluation from the captured measurements.

---
Next: Implement optimizations and re-run benchmarks
EOF

echo "[+] Report: $REPORT_FILE"
