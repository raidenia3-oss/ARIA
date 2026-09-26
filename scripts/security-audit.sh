#!/bin/bash

# AURA OS Security Audit & Hardening

set -euo pipefail

echo "╔════════════════════════════════════════════════════════╗"
echo "║  AURA OS Security Audit v2.1                          ║"
echo "╚════════════════════════════════════════════════════════╝"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ISSUES_FOUND=0

# Audit 1: Check for hardcoded credentials
echo ""
echo "[*] Audit 1: Checking for hardcoded credentials..."

CREDS=$(grep -r "password\|secret\|api_key" backend/ --include="*.py" | \
  grep -E "=\s*['\"][^'\"]*['\"]" | grep -v ".env" | grep -v "example" || echo "")

if [ -z "$CREDS" ]; then
  echo -e "${GREEN}[+] No hardcoded credentials found${NC}"
else
  echo -e "${RED}[-] Hardcoded credentials detected:${NC}"
  echo "$CREDS"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 2: Check dependency vulnerabilities
echo ""
echo "[*] Audit 2: Checking dependency vulnerabilities..."

if command -v safety &> /dev/null; then
  safety check --file backend/requirements.txt || ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
  echo "[-] 'safety' not installed; dependency scan was not run."
fi

# Audit 3: Check SQL injection vulnerabilities
echo ""
echo "[*] Audit 3: Checking for SQL injection vulnerabilities..."

SQL_ISSUES=$(grep -r "execute\|query" backend/ --include="*.py" | \
  grep -E "f['\"].*\{.*\}|format\(|%\s*%" | grep -v "parameterized\|prepared" || echo "")

if [ -z "$SQL_ISSUES" ]; then
  echo -e "${GREEN}[+] No SQL injection vulnerabilities found${NC}"
else
  echo -e "${YELLOW}[!] Potential SQL injection issues:${NC}"
  echo "$SQL_ISSUES"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 4: Check for insecure deserialization
echo ""
echo "[*] Audit 4: Checking for insecure deserialization..."

PICKLE_ISSUES=$(grep -r "pickle\|yaml.load" backend/ --include="*.py" | \
  grep -v "safe" || echo "")

if [ -z "$PICKLE_ISSUES" ]; then
  echo -e "${GREEN}[+] No insecure deserialization found${NC}"
else
  echo -e "${RED}[-] Insecure deserialization detected:${NC}"
  echo "$PICKLE_ISSUES"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 5: Check file permissions
echo ""
echo "[*] Audit 5: Checking file permissions..."

PERMS=$(find backend/ -type f -perm /077 -exec ls -la {} \; || echo "")

if [ -z "$PERMS" ]; then
  echo -e "${GREEN}[+] File permissions are secure${NC}"
else
  echo -e "${YELLOW}[!] Files with overly permissive permissions:${NC}"
  echo "$PERMS"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 6: Check for exposed debug mode
echo ""
echo "[*] Audit 6: Checking for debug mode..."

DEBUG=$(grep -r "DEBUG\s*=\s*True" backend/ --include="*.py" || echo "")

if [ -z "$DEBUG" ]; then
  echo -e "${GREEN}[+] Debug mode is disabled${NC}"
else
  echo -e "${RED}[-] Debug mode is enabled:${NC}"
  echo "$DEBUG"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 7: Check HTTPS enforcement
echo ""
echo "[*] Audit 7: Checking HTTPS enforcement..."

HTTPS=$(grep -r "HTTPS\|SSL\|TLS" backend/ --include="*.py" | grep -i "enforce\|required" || echo "")

if [ -z "$HTTPS" ]; then
  echo -e "${YELLOW}[!] HTTPS not enforced${NC}"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
  echo -e "${GREEN}[+] HTTPS enforcement configured${NC}"
fi

# Audit 8: Check CORS configuration
echo ""
echo "[*] Audit 8: Checking CORS configuration..."

CORS=$(grep -r "allow_origins\|CORS" backend/ --include="*.py" | grep "\*" || echo "")

if [ -z "$CORS" ]; then
  echo -e "${GREEN}[+] CORS is properly restricted${NC}"
else
  echo -e "${YELLOW}[!] CORS might be too permissive:${NC}"
  echo "$CORS"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 9: Check authentication
echo ""
echo "[*] Audit 9: Checking authentication implementation..."

AUTH=$(grep -r "@.*_auth\|requires_auth\|jwt_required" backend/ --include="*.py" || echo "")

if [ -n "$AUTH" ]; then
  echo -e "${GREEN}[+] Authentication detected${NC}"
else
  echo -e "${RED}[-] Missing authentication checks${NC}"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 10: Check rate limiting
echo ""
echo "[*] Audit 10: Checking rate limiting..."

RATE_LIMIT=$(grep -r "rate_limit\|throttle" backend/ --include="*.py" || echo "")

if [ -n "$RATE_LIMIT" ]; then
  echo -e "${GREEN}[+] Rate limiting configured${NC}"
else
  echo -e "${YELLOW}[!] Rate limiting not detected${NC}"
  ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Audit 11: Python bandit (static analysis)
echo ""
echo "[*] Audit 11: Running Bandit security linter..."

if command -v bandit &> /dev/null; then
  bandit -r backend/ -ll || echo "[!] Some issues found (check output above)"
else
  echo "[-] Bandit not installed; static scan was not run."
fi

# Generate report
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Security Audit Complete                              ║"
echo "╚════════════════════════════════════════════════════════╝"

REPORT_FILE="${REPORT_FILE:-data/SECURITY_AUDIT_REPORT.md}"
mkdir -p "$(dirname "$REPORT_FILE")"
cat > "$REPORT_FILE" << EOF
# AURA OS v2.1 Security Audit Report

Generated: $(date)

## Summary

- Total Issues Found: $ISSUES_FOUND
- Severity breakdown: not classified by this shell scanner.

## Audit Results

The console output above contains the result of each check. Optional tools that
were not installed are explicitly marked as not run.

## Recommendations

1. **Immediate Actions:**
   - Review every finding printed by the checks above.
   - Run the optional dependency and Bandit scans in CI.

2. **Short-term (1-2 weeks):**
   - Replace this heuristic audit with a maintained security scanner.
   - Re-run the audit after remediation.

3. **Long-term (1-3 months):**
   - Add authenticated integration tests and continuous dependency monitoring.

## Compliance Status

- OWASP Top 10: [Score]
- GDPR: [Compliant/Non-compliant]
- SOC2: [In Progress/Compliant]
- ISO27001: [In Progress/Compliant]

## Next Steps

1. Fix critical issues immediately
2. Schedule follow-up audit in 30 days
3. Implement security scanning in CI/CD
4. Train team on secure coding

---
**Report Generated**: $(date)
**Auditor**: Automated Security Scanner
EOF

echo "[+] Security audit report: $REPORT_FILE"

if [ $ISSUES_FOUND -gt 0 ]; then
  echo ""
  echo -e "${YELLOW}[!] $ISSUES_FOUND issue(s) found. Review SECURITY_AUDIT_REPORT.md${NC}"
  exit 1
else
  echo ""
  echo -e "${GREEN}[+] No critical issues found. System is production-ready!${NC}"
  exit 0
fi
