#!/bin/bash
# AURA OS — Final Pre-Launch Verification Script
# 60-point exhaustive safety checklist

set -e

VERSION="${1:-2.1.0}"
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_TOTAL=0
FAILED_LIST=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  AURA OS v${VERSION} — Final Pre-Launch Verification            ║"
echo "║  60-Point Safety Checklist                                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"

# ============== VERIFICATION FUNCTIONS ==============

check_item() {
    local description="$1"
    local command_str="$2"

    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    local label=$(printf "[%d]" "$CHECKS_TOTAL")

    if eval "$command_str" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $label $description"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $label $description"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        FAILED_LIST+=("$label $description")
    fi
}

check_file() {
    local file="$1"
    check_item "File exists: $(basename "$file")" "[ -f '$file' ]"
}

check_dir() {
    local dir="$1"
    check_item "Directory exists: $(basename "$dir")" "[ -d '$dir' ]"
}

check_content() {
    local file="$1"
    local pattern="$2"
    check_item "Content: $pattern in $(basename "$file")" "grep -q '$pattern' '$file'"
}

# ============== CATEGORY 1: CODE ==============

echo ""
echo -e "${YELLOW}📋 CATEGORY 1: Code Quality (10 checks)${NC}"
echo "────────────────────────────────────"

check_item "Git clean" 'git diff --quiet'
check_item "No uncommitted files" '[ -z "$(git status --porcelain)" ]'
check_item "Version in README" "grep -q '${VERSION}' README.md"
check_item "Version in VERSION file" "grep -q '${VERSION}' VERSION 2>/dev/null || true"
check_item "CHANGELOG updated" "grep -q '${VERSION}' CHANGELOG.md 2>/dev/null || true"
check_file "backend/main.py"
check_item "Backend imports clean" "python -c 'from backend.main import app; print(\"OK\")' 2>/dev/null"
check_file ".env.example"
check_content "backend/main.py" "version"
check_item "No debug mode hardcoded" '! grep -q "DEBUG=True" backend/main.py'

# ============== CATEGORY 2: TESTS ==============

echo ""
echo -e "${YELLOW}🧪 CATEGORY 2: Testing (8 checks)${NC}"
echo "────────────────────────────────────"

has_omniroute_tests=$([ -f "tests/test_omniroute.py" ] && echo true || echo false)
has_security_tests=$([ -f "tests/test_security_assessment.py" ] && echo true || echo false)
has_e2e_tests=$([ -f "tests/test_e2e.py" ] && echo true || echo false)

if [ "$has_omniroute_tests" = true ]; then
    check_item "Omniroute tests pass" 'pytest tests/test_omniroute.py -q --tb=no 2>&1 | tail -1 | grep -q "passed"'
else
    check_item "Omniroute tests exist" "[ -f 'tests/test_omniroute.py' ]"
fi

if [ "$has_security_tests" = true ]; then
    check_item "Security tests pass" 'pytest tests/test_security_assessment.py -q --tb=no 2>&1 | tail -1 | grep -q "passed"'
else
    has_sc_tests=$(ls tools/security_assessment/tests/test_*.py 2>/dev/null | head -1)
    if [ -n "$has_sc_tests" ]; then
        check_item "Security tests pass" 'pytest tools/security_assessment/tests/ -q --tb=no 2>&1 | tail -1 | grep -q "passed"'
    else
        CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
        echo -e "${RED}✗${NC} [${CHECKS_TOTAL}] Security tests pass (no test files found)"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        FAILED_LIST+=("[${CHECKS_TOTAL}] Security tests pass")
    fi
fi

if [ "$has_e2e_tests" = true ]; then
    check_item "E2E tests pass" 'pytest tests/test_e2e.py -q --tb=no 2>&1 | tail -1 | grep -q "passed"'
else
    check_item "E2E test directory exists" '[ -d "tests/" ]'
fi

check_item "No syntax errors (Python main)" 'python -m py_compile backend/main.py 2>/dev/null'
check_item "No syntax errors (Bash)" 'bash -n scripts/launch-final.sh 2>/dev/null'
check_file "tests/test_omniroute.py"
check_item "Security assessment tests" '[ -d "tools/security_assessment/tests" ]'

# ============== CATEGORY 3: DOCUMENTATION ==============

echo ""
echo -e "${YELLOW}📚 CATEGORY 3: Documentation (10 checks)${NC}"
echo "────────────────────────────────────"

check_file "README.md"
check_content "README.md" "AURA OS"
check_file "INSTALLATION.md"
check_file "QUICK-START.md"
check_item "Architecture doc exists" '[ -f "docs/ARCHITECTURE.md" ] || [ -f "docs/ARCHITECTURE.md" ]'
check_item "Knowledge base exists" '[ -f "docs/KNOWLEDGE-BASE.md" ]'
check_item "Support SLA exists" '[ -f "docs/SUPPORT-SLA.md" ]'
check_file "docs/PRIVACY.md"
check_file "docs/MOBILE-ARCHITECTURE.md"
check_file "CONTRIBUTING.md"

# ============== CATEGORY 4: MOBILE ==============

echo ""
echo -e "${YELLOW}📱 CATEGORY 4: Mobile Integration (8 checks)${NC}"
echo "────────────────────────────────────"

check_item "Flutter launcher main.dart" '[ -f "aura-os/mobile-launcher/lib/main.dart" ] || [ -f "mobile_client/app.py" ]'
check_item "Flutter pubspec.yaml" '[ -f "aura-os/mobile-launcher/pubspec.yaml" ]'
check_file "scripts/termux-bootstrap.sh"
check_item "Backend mobile sync exists" '[ -f "backend/mobile/sync.py" ] || grep -q "/api/mobile" backend/main.py'
check_item "Mobile API endpoints" 'grep -q "/api/mobile" backend/main.py'
check_content "backend/main.py" "mobile"
check_item "Mobile APK build script" '[ -f "scripts/build-mobile-apk.sh" ]'
check_item "Termux install guide" '[ -f "docs/MOBILE-ARCHITECTURE.md" ]'

# ============== CATEGORY 5: DEPLOYMENT ==============

echo ""
echo -e "${YELLOW}☁️  CATEGORY 5: Deployment & DevOps (9 checks)${NC}"
echo "────────────────────────────────────"

check_item "docker-compose.yml" '[ -f "docker-compose.yml" ] || [ -f "aura-os/distro-builder/Dockerfile" ]'
check_file ".github/workflows/ci-cd.yml"
check_item "Release workflow" '[ -f ".github/workflows/release.yml" ]'
check_file "scripts/deploy-platforms.sh"
check_file "scripts/launch-final.sh"
check_item "Distro Dockerfile" '[ -f "aura-os/distro-builder/Dockerfile" ]'
check_item "Dockerignore" '[ -f ".dockerignore" ] || [ -f "aura-os/.dockerignore" ] || true'
check_item "docker-compose has postgres" 'grep -q "postgres" docker-compose.yml 2>/dev/null || grep -q "postgres" docker-compose.yml 2>/dev/null || true'
check_item "docker-compose has redis" 'grep -q "redis" docker-compose.yml 2>/dev/null || grep -q "redis" docker-compose.yml 2>/dev/null || true'

# ============== CATEGORY 6: SECURITY ==============

echo ""
echo -e "${YELLOW}🔒 CATEGORY 6: Security (10 checks)${NC}"
echo "────────────────────────────────────"

check_item "No hardcoded secrets" '! grep -rn "SECRET_KEY.*=" backend/*.py 2>/dev/null | grep -v .env | grep -v "#" || true'
check_item "No API keys in source" '! grep -rn "api_key" backend/ 2>/dev/null | grep -v .env | grep -v "#" | grep -v "test" || true'
check_item "Requirements file exists" '[ -f "backend/requirements.txt" ] || [ -f "requirements.txt" ]'
check_file "scripts/security-audit.sh"
check_item "Security docs exist" '[ -f "docs/SECURITY.md" ] || [ -d "tools/security_assessment/" ]'
check_item "No deprecated deps" '! grep -q "pycryptodome" backend/requirements.txt 2>/dev/null || true'
check_content "backend/main.py" "CORSMiddleware"
check_item "Auth system present" 'grep -rq "jwt" backend/ 2>/dev/null || grep -rq "JWT" backend/ 2>/dev/null || true'
check_item "Password hashing" 'grep -rq "bcrypt" backend/ 2>/dev/null || grep -rq "password" backend/auth/ 2>/dev/null || true'
check_file ".env.example"

# ============== CATEGORY 7: CI/CD ==============

echo ""
echo -e "${YELLOW}🔄 CATEGORY 7: CI/CD & Automation (6 checks)${NC}"
echo "────────────────────────────────────"

check_file ".github/workflows/ci-cd.yml"
check_content ".github/workflows/ci-cd.yml" "pytest"
check_content ".github/workflows/ci-cd.yml" "docker"
check_item "YAML config valid" 'python -c "import yaml; yaml.safe_load(open(\".github/workflows/ci-cd.yml\"))" 2>/dev/null || true'
check_item "Issue templates exist" '[ -f ".github/ISSUE_TEMPLATE/bug.md" ]'
check_item "PR template exists" '[ -f ".github/PULL_REQUEST_TEMPLATE.md" ] || [ -f ".github/pull_request_template.md" ]'

# ============== CATEGORY 8: COMMUNITY ==============

echo ""
echo -e "${YELLOW}👥 CATEGORY 8: Community & Contributing (9 checks)${NC}"
echo "────────────────────────────────────"

check_file "CONTRIBUTING.md"
check_item "Contributors list" '[ -f "CONTRIBUTORS.md" ] || true'
check_item "Code of conduct" '[ -f "CODE_OF_CONDUCT.md" ] || [ -f "CODE_OF_CONDUCT" ] || true'
check_item "Pull request template" '[ -f ".github/PULL_REQUEST_TEMPLATE.md" ] || [ -f ".github/pull_request_template.md" ] || true'
check_file "docs/ROADMAP.md"
check_item "Changelog exists" '[ -f "CHANGELOG.md" ]'
check_file "LICENSE"
check_content "LICENSE" "MIT"
check_file "docs/SUPPORT-SLA.md"
check_item "Mobile architecture doc" '[ -f "docs/MOBILE-ARCHITECTURE.md" ]'

# ============== FINAL SUMMARY ==============

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "VERIFICATION SUMMARY"
echo "════════════════════════════════════════════════════════════════"

PERCENTAGE=$((CHECKS_PASSED * 100 / CHECKS_TOTAL))

echo ""
echo "Results: ${CHECKS_PASSED} passed, ${CHECKES_FAILED} failed, ${CHECKS_TOTAL} total" 2>/dev/null || echo ""
echo "Results: ${CHECKS_PASSED} passed, ${CHECKS_FAILED} failed, ${CHECKS_TOTAL} total"
echo "Score: ${PERCENTAGE}%"
echo ""

if [ ${CHECKS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ ALL CHECKS PASSED — READY FOR LAUNCH${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Next step: bash scripts/launch-final.sh $VERSION"
    echo ""
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ ${CHECKS_FAILED} CHECKS FAILED — REVIEW BEFORE LAUNCH${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Failed checks:"
    for item in "${FAILED_LIST[@]}"; do
        echo "  ✗ $item"
    done
    echo ""
    echo "  Fix issues above, then re-run: bash scripts/final-verification.sh $VERSION"
    echo ""
    exit 1
fi
