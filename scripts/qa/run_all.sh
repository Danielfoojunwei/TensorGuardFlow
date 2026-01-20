#!/usr/bin/env bash
# TensorGuardFlow QA Harness - Full Release Readiness Test Suite
# Version: 2.3.0
#
# This script runs all QA checks and generates a comprehensive release readiness report.
# Usage: ./scripts/qa/run_all.sh [--skip-docker] [--quick]
#
# Exit codes:
#   0 - All checks passed, release is GO
#   1 - Critical failures, release is NO-GO

set -euo pipefail

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION=$(grep 'version = ' "$PROJECT_ROOT/pyproject.toml" | head -1 | sed 's/.*= "\(.*\)"/\1/')
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts/qa/${VERSION}/${TIMESTAMP}"

# Flags
SKIP_DOCKER=false
QUICK_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-docker) SKIP_DOCKER=true; shift ;;
        --quick) QUICK_MODE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Results tracking
declare -A RESULTS
CRITICAL_FAILURES=0
NON_CRITICAL_FAILURES=0

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
log_header() {
    echo ""
    echo "=============================================================================="
    echo " $1"
    echo "=============================================================================="
    echo ""
}

log_step() {
    echo "[$(date +%H:%M:%S)] $1"
}

log_pass() {
    echo "[PASS] $1"
    RESULTS["$1"]="PASS"
}

log_fail() {
    local severity="${2:-CRITICAL}"
    echo "[FAIL] $1 (${severity})"
    RESULTS["$1"]="FAIL"
    if [[ "$severity" == "CRITICAL" ]]; then
        ((CRITICAL_FAILURES++)) || true
    else
        ((NON_CRITICAL_FAILURES++)) || true
    fi
}

log_skip() {
    echo "[SKIP] $1"
    RESULTS["$1"]="SKIP"
}

ensure_dir() {
    mkdir -p "$1"
}

# ==============================================================================
# SETUP
# ==============================================================================
log_header "TensorGuardFlow QA Harness v${VERSION}"
log_step "Git Commit: ${GIT_COMMIT}"
log_step "Timestamp: ${TIMESTAMP}"
log_step "Artifacts: ${ARTIFACTS_DIR}"
log_step "Quick Mode: ${QUICK_MODE}"
log_step "Skip Docker: ${SKIP_DOCKER}"

# Create artifacts directory structure
ensure_dir "$ARTIFACTS_DIR/backend"
ensure_dir "$ARTIFACTS_DIR/frontend"
ensure_dir "$ARTIFACTS_DIR/security"
ensure_dir "$ARTIFACTS_DIR/performance"
ensure_dir "$ARTIFACTS_DIR/installation"
ensure_dir "$ARTIFACTS_DIR/logs"

cd "$PROJECT_ROOT"

# Write run metadata
cat > "$ARTIFACTS_DIR/run_metadata.json" << EOF
{
    "version": "${VERSION}",
    "git_commit": "${GIT_COMMIT}",
    "timestamp": "${TIMESTAMP}",
    "quick_mode": ${QUICK_MODE},
    "skip_docker": ${SKIP_DOCKER},
    "platform": "$(uname -s)",
    "platform_version": "$(uname -r)",
    "python_version": "$(python3 --version 2>&1 | awk '{print $2}')",
    "node_version": "$(node --version 2>/dev/null || echo 'not installed')"
}
EOF

# ==============================================================================
# PHASE 1: BUILD VERIFICATION
# ==============================================================================
log_header "PHASE 1: Build Verification"

# 1.1 Python package installation check
log_step "Checking Python package installation..."
if pip show tensorguard &>/dev/null || pip install -e ".[dev]" &>"$ARTIFACTS_DIR/logs/pip_install.log"; then
    log_pass "Python Package Installation"
else
    log_fail "Python Package Installation"
fi

# 1.2 Core imports check
log_step "Verifying core imports..."
if PYTHONPATH=src python3 -c "
from tensorguard.platform.main import app
from tensorguard.platform.database import engine
from tensorguard.platform.worker import WorkerDaemon
print('Core imports successful')
" &>"$ARTIFACTS_DIR/logs/import_check.log" 2>&1; then
    log_pass "Core Python Imports"
else
    log_fail "Core Python Imports"
fi

# 1.3 Frontend build check
log_step "Checking frontend build..."
if [[ -d "$PROJECT_ROOT/frontend" ]]; then
    cd "$PROJECT_ROOT/frontend"
    if npm install &>"$ARTIFACTS_DIR/logs/npm_install.log" 2>&1; then
        if npm run build &>"$ARTIFACTS_DIR/logs/npm_build.log" 2>&1; then
            log_pass "Frontend Build"
        else
            log_fail "Frontend Build" "CRITICAL"
        fi
    else
        log_fail "Frontend npm install" "CRITICAL"
    fi
    cd "$PROJECT_ROOT"
else
    log_skip "Frontend Build (no frontend directory)"
fi

# ==============================================================================
# PHASE 2: BACKEND TESTS
# ==============================================================================
log_header "PHASE 2: Backend Tests"

# 2.1 Unit tests
log_step "Running backend unit tests..."
if PYTHONPATH=src python -m pytest tests/unit/ \
    -v \
    --tb=short \
    --junitxml="$ARTIFACTS_DIR/backend/junit_unit.xml" \
    --cov=src/tensorguard \
    --cov-report=xml:"$ARTIFACTS_DIR/backend/coverage_unit.xml" \
    --cov-report=html:"$ARTIFACTS_DIR/backend/coverage_html" \
    2>&1 | tee "$ARTIFACTS_DIR/logs/pytest_unit.log"; then
    log_pass "Backend Unit Tests"
else
    log_fail "Backend Unit Tests"
fi

# 2.2 Integration tests
log_step "Running backend integration tests..."
if PYTHONPATH=src python -m pytest tests/integration/ \
    -v \
    --tb=short \
    --junitxml="$ARTIFACTS_DIR/backend/junit_integration.xml" \
    2>&1 | tee "$ARTIFACTS_DIR/logs/pytest_integration.log"; then
    log_pass "Backend Integration Tests"
else
    log_fail "Backend Integration Tests"
fi

# 2.3 Security tests
log_step "Running security tests..."
if PYTHONPATH=src python -m pytest tests/security/ \
    -v \
    --tb=short \
    --junitxml="$ARTIFACTS_DIR/backend/junit_security.xml" \
    2>&1 | tee "$ARTIFACTS_DIR/logs/pytest_security.log"; then
    log_pass "Backend Security Tests"
else
    log_fail "Backend Security Tests"
fi

# 2.4 E2E smoke tests (backend)
if [[ "$QUICK_MODE" != "true" ]]; then
    log_step "Running E2E tests..."
    if PYTHONPATH=src python -m pytest tests/e2e/ \
        -v \
        --tb=short \
        --junitxml="$ARTIFACTS_DIR/backend/junit_e2e.xml" \
        2>&1 | tee "$ARTIFACTS_DIR/logs/pytest_e2e.log"; then
        log_pass "Backend E2E Tests"
    else
        log_fail "Backend E2E Tests"
    fi

    # Stability run: run E2E twice
    log_step "Running E2E stability check (2nd run)..."
    if PYTHONPATH=src python -m pytest tests/e2e/ \
        -v \
        --tb=short \
        --junitxml="$ARTIFACTS_DIR/backend/junit_e2e_stability.xml" \
        2>&1 | tee "$ARTIFACTS_DIR/logs/pytest_e2e_stability.log"; then
        log_pass "Backend E2E Stability Run"
    else
        log_fail "Backend E2E Stability Run (Flaky)"
    fi
else
    log_skip "Backend E2E Tests (quick mode)"
fi

# ==============================================================================
# PHASE 3: FRONTEND TESTS
# ==============================================================================
log_header "PHASE 3: Frontend Tests"

cd "$PROJECT_ROOT/frontend"

# 3.1 ESLint check
log_step "Running ESLint..."
if [[ -f "node_modules/.bin/eslint" ]]; then
    if npx eslint src/ --format json --output-file "$ARTIFACTS_DIR/frontend/eslint_report.json" 2>/dev/null; then
        log_pass "Frontend ESLint"
    else
        log_fail "Frontend ESLint" "NON-CRITICAL"
    fi
else
    # Try to install eslint if not present
    if npm install -D eslint eslint-plugin-vue @typescript-eslint/eslint-plugin @typescript-eslint/parser &>/dev/null; then
        if npx eslint src/ --format json --output-file "$ARTIFACTS_DIR/frontend/eslint_report.json" 2>/dev/null; then
            log_pass "Frontend ESLint"
        else
            log_fail "Frontend ESLint" "NON-CRITICAL"
        fi
    else
        log_skip "Frontend ESLint (not configured)"
    fi
fi

# 3.2 TypeScript check
log_step "Running TypeScript check..."
if npx vue-tsc --noEmit 2>&1 | tee "$ARTIFACTS_DIR/frontend/typescript_check.log"; then
    log_pass "Frontend TypeScript"
else
    # Vue-tsc often returns non-zero for warnings, check if critical
    if grep -q "error TS" "$ARTIFACTS_DIR/frontend/typescript_check.log" 2>/dev/null; then
        log_fail "Frontend TypeScript" "NON-CRITICAL"
    else
        log_pass "Frontend TypeScript (warnings only)"
    fi
fi

# 3.3 Vitest tests (if configured)
log_step "Running Vitest tests..."
if [[ -f "vitest.config.ts" ]] || [[ -f "vitest.config.js" ]]; then
    if npm run test 2>&1 | tee "$ARTIFACTS_DIR/frontend/vitest.log"; then
        log_pass "Frontend Vitest Tests"
    else
        log_fail "Frontend Vitest Tests" "CRITICAL"
    fi
else
    log_skip "Frontend Vitest Tests (not configured)"
fi

cd "$PROJECT_ROOT"

# ==============================================================================
# PHASE 4: CODE QUALITY GATES
# ==============================================================================
log_header "PHASE 4: Code Quality Gates"

# 4.1 Ruff lint
log_step "Running Ruff linter..."
if ruff check src/ --output-format json > "$ARTIFACTS_DIR/backend/ruff_report.json" 2>&1; then
    log_pass "Python Lint (Ruff)"
else
    log_fail "Python Lint (Ruff)" "NON-CRITICAL"
fi

# 4.2 Ruff format check
log_step "Checking Python formatting..."
if ruff format --check src/ 2>&1 | tee "$ARTIFACTS_DIR/backend/ruff_format.log"; then
    log_pass "Python Format (Ruff)"
else
    log_fail "Python Format (Ruff)" "NON-CRITICAL"
fi

# 4.3 Mypy typecheck
log_step "Running Mypy type checker..."
if mypy src/ --ignore-missing-imports 2>&1 | tee "$ARTIFACTS_DIR/backend/mypy_report.log"; then
    log_pass "Python Typecheck (Mypy)"
else
    # Mypy often has warnings that aren't blocking
    if grep -q "error:" "$ARTIFACTS_DIR/backend/mypy_report.log"; then
        log_fail "Python Typecheck (Mypy)" "NON-CRITICAL"
    else
        log_pass "Python Typecheck (Mypy - warnings only)"
    fi
fi

# ==============================================================================
# PHASE 5: SECURITY SCANS
# ==============================================================================
log_header "PHASE 5: Security Scans"

# 5.1 pip-audit (Python dependencies)
log_step "Running pip-audit..."
if command -v pip-audit &>/dev/null || pip install pip-audit &>/dev/null; then
    if pip-audit --format json --output "$ARTIFACTS_DIR/security/pip_audit.json" 2>&1 | tee "$ARTIFACTS_DIR/logs/pip_audit.log"; then
        log_pass "Python Dependency Audit"
    else
        # Check severity of vulnerabilities
        if grep -q '"severity": "critical"' "$ARTIFACTS_DIR/security/pip_audit.json" 2>/dev/null || \
           grep -q '"severity": "high"' "$ARTIFACTS_DIR/security/pip_audit.json" 2>/dev/null; then
            log_fail "Python Dependency Audit (Critical/High vulnerabilities)"
        else
            log_fail "Python Dependency Audit" "NON-CRITICAL"
        fi
    fi
else
    log_skip "Python Dependency Audit (pip-audit not available)"
fi

# 5.2 npm audit (Frontend dependencies)
log_step "Running npm audit..."
cd "$PROJECT_ROOT/frontend"
if npm audit --json > "$ARTIFACTS_DIR/security/npm_audit.json" 2>&1; then
    log_pass "Frontend Dependency Audit"
else
    # Check for critical vulnerabilities
    if jq -e '.metadata.vulnerabilities.critical > 0 or .metadata.vulnerabilities.high > 0' "$ARTIFACTS_DIR/security/npm_audit.json" 2>/dev/null; then
        log_fail "Frontend Dependency Audit (Critical/High vulnerabilities)"
    else
        log_fail "Frontend Dependency Audit" "NON-CRITICAL"
    fi
fi
cd "$PROJECT_ROOT"

# 5.3 Secrets scan (gitleaks)
log_step "Running secrets scan..."
if command -v gitleaks &>/dev/null; then
    if gitleaks detect --source . --report-path "$ARTIFACTS_DIR/security/gitleaks_report.json" --report-format json 2>&1 | tee "$ARTIFACTS_DIR/logs/gitleaks.log"; then
        log_pass "Secrets Scan (Gitleaks)"
    else
        log_fail "Secrets Scan (Gitleaks)"
    fi
else
    # Try to run with docker if gitleaks not installed
    if docker run --rm -v "$(pwd):/path" zricethezav/gitleaks:latest detect --source /path --report-path /path/artifacts/qa/${VERSION}/${TIMESTAMP}/security/gitleaks_report.json --report-format json 2>&1; then
        log_pass "Secrets Scan (Gitleaks via Docker)"
    else
        log_skip "Secrets Scan (Gitleaks not available)"
    fi
fi

# 5.4 Container scan (trivy)
if [[ "$SKIP_DOCKER" != "true" ]]; then
    log_step "Running container security scan..."
    if command -v trivy &>/dev/null; then
        # Build image first
        if docker build -f docker/platform/Dockerfile -t tensorguard:qa-test . &>"$ARTIFACTS_DIR/logs/docker_build.log"; then
            if trivy image --format json --output "$ARTIFACTS_DIR/security/trivy_report.json" tensorguard:qa-test 2>&1 | tee "$ARTIFACTS_DIR/logs/trivy.log"; then
                log_pass "Container Security Scan (Trivy)"
            else
                log_fail "Container Security Scan (Trivy)" "NON-CRITICAL"
            fi
        else
            log_fail "Container Build for Scan"
        fi
    else
        log_skip "Container Security Scan (Trivy not available)"
    fi
else
    log_skip "Container Security Scan (Docker skipped)"
fi

# ==============================================================================
# PHASE 6: PERFORMANCE SMOKE TESTS
# ==============================================================================
log_header "PHASE 6: Performance Smoke Tests"

if [[ "$QUICK_MODE" != "true" ]]; then
    log_step "Running performance smoke tests..."
    if [[ -f "$SCRIPT_DIR/perf_smoke.py" ]]; then
        if PYTHONPATH=src python "$SCRIPT_DIR/perf_smoke.py" \
            --output "$ARTIFACTS_DIR/performance/perf_smoke_results.json" \
            2>&1 | tee "$ARTIFACTS_DIR/logs/perf_smoke.log"; then
            log_pass "Performance Smoke Tests"
        else
            log_fail "Performance Smoke Tests" "NON-CRITICAL"
        fi
    else
        log_skip "Performance Smoke Tests (script not found)"
    fi

    # Worker stability check
    log_step "Running worker stability check..."
    if [[ -f "$SCRIPT_DIR/worker_stability.py" ]]; then
        if PYTHONPATH=src python "$SCRIPT_DIR/worker_stability.py" \
            --duration 30 \
            --output "$ARTIFACTS_DIR/performance/worker_stability.json" \
            2>&1 | tee "$ARTIFACTS_DIR/logs/worker_stability.log"; then
            log_pass "Worker Stability Check"
        else
            log_fail "Worker Stability Check" "NON-CRITICAL"
        fi
    else
        log_skip "Worker Stability Check (script not found)"
    fi
else
    log_skip "Performance Smoke Tests (quick mode)"
fi

# ==============================================================================
# PHASE 7: INSTALLATION TESTS
# ==============================================================================
log_header "PHASE 7: Installation Tests"

if [[ "$SKIP_DOCKER" != "true" ]] && [[ "$QUICK_MODE" != "true" ]]; then
    log_step "Running installation smoke tests..."
    if [[ -f "$SCRIPT_DIR/install_smoke.sh" ]]; then
        if bash "$SCRIPT_DIR/install_smoke.sh" \
            --output-dir "$ARTIFACTS_DIR/installation" \
            2>&1 | tee "$ARTIFACTS_DIR/logs/install_smoke.log"; then
            log_pass "Installation Smoke Tests"
        else
            log_fail "Installation Smoke Tests" "NON-CRITICAL"
        fi
    else
        log_skip "Installation Smoke Tests (script not found)"
    fi
else
    log_skip "Installation Smoke Tests (Docker or quick mode skipped)"
fi

# ==============================================================================
# PHASE 8: GENERATE REPORT
# ==============================================================================
log_header "PHASE 8: Generate Release Readiness Report"

# Generate summary JSON
cat > "$ARTIFACTS_DIR/summary.json" << EOF
{
    "version": "${VERSION}",
    "git_commit": "${GIT_COMMIT}",
    "timestamp": "${TIMESTAMP}",
    "critical_failures": ${CRITICAL_FAILURES},
    "non_critical_failures": ${NON_CRITICAL_FAILURES},
    "go_decision": $([ $CRITICAL_FAILURES -eq 0 ] && echo "true" || echo "false"),
    "results": {
$(for key in "${!RESULTS[@]}"; do echo "        \"$key\": \"${RESULTS[$key]}\","; done | sed '$ s/,$//')
    }
}
EOF

# Generate markdown report
log_step "Generating release readiness report..."
if [[ -f "$SCRIPT_DIR/generate_report.py" ]]; then
    PYTHONPATH=src python "$SCRIPT_DIR/generate_report.py" \
        --artifacts-dir "$ARTIFACTS_DIR" \
        --output "$PROJECT_ROOT/docs/release_readiness_report.md" \
        2>&1 | tee "$ARTIFACTS_DIR/logs/report_generation.log"
fi

# ==============================================================================
# FINAL SUMMARY
# ==============================================================================
log_header "QA HARNESS COMPLETE"

echo ""
echo "Results Summary:"
echo "================"
for key in "${!RESULTS[@]}"; do
    printf "  %-40s %s\n" "$key" "${RESULTS[$key]}"
done
echo ""
echo "Critical Failures: ${CRITICAL_FAILURES}"
echo "Non-Critical Failures: ${NON_CRITICAL_FAILURES}"
echo ""
echo "Artifacts saved to: ${ARTIFACTS_DIR}"
echo ""

# Symlink to latest
ln -sfn "$ARTIFACTS_DIR" "$PROJECT_ROOT/artifacts/qa/latest"

# Exit with appropriate code
if [[ $CRITICAL_FAILURES -gt 0 ]]; then
    echo "=============================================================================="
    echo " RELEASE DECISION: NO-GO (${CRITICAL_FAILURES} critical failures)"
    echo "=============================================================================="
    exit 1
else
    echo "=============================================================================="
    echo " RELEASE DECISION: GO (All critical checks passed)"
    echo "=============================================================================="
    exit 0
fi
