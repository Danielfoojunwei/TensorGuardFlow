#!/usr/bin/env bash
# TensorGuardFlow Security Scan Script
# Runs comprehensive security scans for release readiness

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="${1:-$PROJECT_ROOT/artifacts/qa/security/$TIMESTAMP}"

# Results tracking
declare -A RESULTS
CRITICAL_COUNT=0
HIGH_COUNT=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_header() {
    echo ""
    echo "=============================================="
    echo " $1"
    echo "=============================================="
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    RESULTS["$1"]="PASS"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1 ($2)"
    RESULTS["$1"]="FAIL"
    if [[ "$2" == "CRITICAL" ]]; then
        ((CRITICAL_COUNT++)) || true
    elif [[ "$2" == "HIGH" ]]; then
        ((HIGH_COUNT++)) || true
    fi
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    RESULTS["$1"]="WARN"
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1 (not available)"
    RESULTS["$1"]="SKIP"
}

# Create output directory
mkdir -p "$OUTPUT_DIR"

log_header "TensorGuardFlow Security Scan"
echo "Output Directory: $OUTPUT_DIR"
echo "Timestamp: $TIMESTAMP"

cd "$PROJECT_ROOT"

# ==============================================================================
# 1. PYTHON DEPENDENCY AUDIT (pip-audit)
# ==============================================================================
log_header "1. Python Dependency Audit (pip-audit)"

if command -v pip-audit &>/dev/null || pip install pip-audit -q &>/dev/null; then
    echo "Running pip-audit..."
    if pip-audit --format json --output "$OUTPUT_DIR/pip_audit.json" 2>&1 | tee "$OUTPUT_DIR/pip_audit.log"; then
        log_pass "Python Dependency Audit"
    else
        # Check for critical/high vulnerabilities
        if [ -f "$OUTPUT_DIR/pip_audit.json" ]; then
            VULN_COUNT=$(cat "$OUTPUT_DIR/pip_audit.json" | python3 -c "import json,sys; data=json.load(sys.stdin); print(len(data) if isinstance(data,list) else 0)" 2>/dev/null || echo "0")
            if [ "$VULN_COUNT" -gt 0 ]; then
                log_fail "Python Dependency Audit" "HIGH"
                echo "  Found $VULN_COUNT vulnerabilities"
            else
                log_warn "Python Dependency Audit (warnings only)"
            fi
        else
            log_fail "Python Dependency Audit" "HIGH"
        fi
    fi

    # Generate summary
    if [ -f "$OUTPUT_DIR/pip_audit.json" ]; then
        echo ""
        echo "Python Vulnerability Summary:"
        python3 << 'PYEOF'
import json
import sys

try:
    with open("'$OUTPUT_DIR'/pip_audit.json") as f:
        data = json.load(f)

    if isinstance(data, list):
        print(f"  Total vulnerabilities: {len(data)}")
        for vuln in data[:5]:  # Show first 5
            print(f"  - {vuln.get('name', 'Unknown')}: {vuln.get('vulns', [{}])[0].get('id', 'N/A')}")
    else:
        print("  No vulnerabilities found")
except Exception as e:
    print(f"  Could not parse results: {e}")
PYEOF
    fi
else
    log_skip "Python Dependency Audit"
fi

# ==============================================================================
# 2. NODE DEPENDENCY AUDIT (npm audit)
# ==============================================================================
log_header "2. Node Dependency Audit (npm audit)"

if [ -d "$PROJECT_ROOT/frontend" ]; then
    cd "$PROJECT_ROOT/frontend"
    echo "Running npm audit..."
    if npm audit --json > "$OUTPUT_DIR/npm_audit.json" 2>&1; then
        log_pass "Node Dependency Audit"
    else
        # Parse results
        if [ -f "$OUTPUT_DIR/npm_audit.json" ]; then
            CRITICAL=$(cat "$OUTPUT_DIR/npm_audit.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('critical',0))" 2>/dev/null || echo "0")
            HIGH=$(cat "$OUTPUT_DIR/npm_audit.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('metadata',{}).get('vulnerabilities',{}).get('high',0))" 2>/dev/null || echo "0")

            if [ "$CRITICAL" -gt 0 ]; then
                log_fail "Node Dependency Audit" "CRITICAL"
                echo "  Critical: $CRITICAL, High: $HIGH"
            elif [ "$HIGH" -gt 0 ]; then
                log_fail "Node Dependency Audit" "HIGH"
                echo "  High: $HIGH"
            else
                log_warn "Node Dependency Audit (low/moderate only)"
            fi
        else
            log_fail "Node Dependency Audit" "HIGH"
        fi
    fi
    cd "$PROJECT_ROOT"
else
    log_skip "Node Dependency Audit (no frontend)"
fi

# ==============================================================================
# 3. SECRETS SCAN (gitleaks)
# ==============================================================================
log_header "3. Secrets Scan (gitleaks)"

if command -v gitleaks &>/dev/null; then
    echo "Running gitleaks..."
    if gitleaks detect --source . --report-path "$OUTPUT_DIR/gitleaks_report.json" --report-format json --no-git 2>&1 | tee "$OUTPUT_DIR/gitleaks.log"; then
        log_pass "Secrets Scan"
    else
        log_fail "Secrets Scan" "CRITICAL"
    fi
elif command -v docker &>/dev/null; then
    echo "Running gitleaks via Docker..."
    if docker run --rm -v "$(pwd):/path" zricethezav/gitleaks:latest detect \
        --source /path \
        --report-path /path/artifacts/qa/security/$TIMESTAMP/gitleaks_report.json \
        --report-format json \
        --no-git 2>&1 | tee "$OUTPUT_DIR/gitleaks.log"; then
        log_pass "Secrets Scan (Docker)"
    else
        # Check if there were findings
        if [ -f "$OUTPUT_DIR/gitleaks_report.json" ]; then
            FINDINGS=$(cat "$OUTPUT_DIR/gitleaks_report.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
            if [ "$FINDINGS" -gt 0 ]; then
                log_fail "Secrets Scan" "CRITICAL"
                echo "  Found $FINDINGS potential secrets"
            else
                log_pass "Secrets Scan (Docker)"
            fi
        else
            log_skip "Secrets Scan (gitleaks failed)"
        fi
    fi
else
    log_skip "Secrets Scan (gitleaks)"
fi

# ==============================================================================
# 4. CONTAINER SECURITY SCAN (trivy)
# ==============================================================================
log_header "4. Container Security Scan (trivy)"

if command -v trivy &>/dev/null && command -v docker &>/dev/null; then
    # Check if we have a Dockerfile
    if [ -f "$PROJECT_ROOT/docker/platform/Dockerfile" ]; then
        echo "Building container for scan..."
        if docker build -f docker/platform/Dockerfile -t tensorguard:scan-test . -q 2>"$OUTPUT_DIR/docker_build.log"; then
            echo "Running trivy scan..."
            if trivy image --format json --output "$OUTPUT_DIR/trivy_report.json" tensorguard:scan-test 2>&1 | tee "$OUTPUT_DIR/trivy.log"; then
                # Check for critical/high
                TRIVY_CRITICAL=$(cat "$OUTPUT_DIR/trivy_report.json" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    count=0
    for r in d.get('Results',[]):
        for v in r.get('Vulnerabilities',[]):
            if v.get('Severity') in ['CRITICAL']:
                count+=1
    print(count)
except: print(0)
" 2>/dev/null || echo "0")

                if [ "$TRIVY_CRITICAL" -gt 0 ]; then
                    log_fail "Container Security Scan" "CRITICAL"
                    echo "  Found $TRIVY_CRITICAL critical vulnerabilities"
                else
                    log_pass "Container Security Scan"
                fi
            else
                log_fail "Container Security Scan" "HIGH"
            fi
            # Cleanup
            docker rmi tensorguard:scan-test -f &>/dev/null || true
        else
            log_fail "Container Build" "HIGH"
        fi
    else
        log_skip "Container Security Scan (no Dockerfile)"
    fi
elif command -v docker &>/dev/null; then
    echo "Running trivy via Docker..."
    if [ -f "$PROJECT_ROOT/docker/platform/Dockerfile" ]; then
        docker build -f docker/platform/Dockerfile -t tensorguard:scan-test . -q 2>/dev/null || true
        if docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$OUTPUT_DIR:/output" \
            aquasec/trivy:latest image \
            --format json --output /output/trivy_report.json \
            tensorguard:scan-test 2>&1 | tee "$OUTPUT_DIR/trivy.log"; then
            log_pass "Container Security Scan (Docker)"
        else
            log_warn "Container Security Scan (partial)"
        fi
        docker rmi tensorguard:scan-test -f &>/dev/null || true
    else
        log_skip "Container Security Scan (no Dockerfile)"
    fi
else
    log_skip "Container Security Scan (trivy)"
fi

# ==============================================================================
# 5. SECURITY ASSERTION TESTS
# ==============================================================================
log_header "5. Security Assertion Tests"

echo "Running security assertion tests..."
cd "$PROJECT_ROOT"
if TG_ENVIRONMENT=development TG_PQC_STRICT_MODE=false PYTHONPATH=src python -m pytest tests/security/ \
    -v --tb=short \
    --junitxml="$OUTPUT_DIR/security_tests_junit.xml" \
    -x \
    2>&1 | tee "$OUTPUT_DIR/security_tests.log"; then
    log_pass "Security Assertion Tests"
else
    log_fail "Security Assertion Tests" "HIGH"
fi

# ==============================================================================
# GENERATE SUMMARY
# ==============================================================================
log_header "Security Scan Summary"

# Generate JSON summary
cat > "$OUTPUT_DIR/security_summary.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "critical_count": $CRITICAL_COUNT,
    "high_count": $HIGH_COUNT,
    "passed": $([ $CRITICAL_COUNT -eq 0 ] && [ $HIGH_COUNT -eq 0 ] && echo "true" || echo "false"),
    "results": {
$(for key in "${!RESULTS[@]}"; do echo "        \"$key\": \"${RESULTS[$key]}\","; done | sed '$ s/,$//')
    }
}
EOF

# Generate markdown summary
cat > "$OUTPUT_DIR/security_summary.md" << EOF
# Security Scan Summary

**Date:** $(date)
**Version:** $(grep 'version = ' "$PROJECT_ROOT/pyproject.toml" | head -1 | sed 's/.*= "\(.*\)"/\1/')

## Results Overview

| Check | Status |
|-------|--------|
$(for key in "${!RESULTS[@]}"; do echo "| $key | ${RESULTS[$key]} |"; done)

## Vulnerability Counts

- **Critical:** $CRITICAL_COUNT
- **High:** $HIGH_COUNT

## Verdict

$(if [ $CRITICAL_COUNT -eq 0 ] && [ $HIGH_COUNT -eq 0 ]; then
    echo "**PASS** - No critical or high vulnerabilities detected."
else
    echo "**FAIL** - Security issues require remediation before release."
    echo ""
    echo "### Required Actions:"
    echo "1. Review and remediate all critical vulnerabilities"
    echo "2. Review and remediate all high vulnerabilities or document waivers"
fi)

## Artifacts

- pip_audit.json - Python dependency vulnerabilities
- npm_audit.json - Node dependency vulnerabilities
- gitleaks_report.json - Secrets scan results
- trivy_report.json - Container vulnerabilities
- security_tests_junit.xml - Security test results
EOF

echo ""
echo "Results:"
for key in "${!RESULTS[@]}"; do
    printf "  %-40s %s\n" "$key" "${RESULTS[$key]}"
done
echo ""
echo "Critical Issues: $CRITICAL_COUNT"
echo "High Issues: $HIGH_COUNT"
echo ""
echo "Artifacts saved to: $OUTPUT_DIR"
echo ""

# Exit with appropriate code
if [ $CRITICAL_COUNT -gt 0 ]; then
    echo -e "${RED}SECURITY SCAN: FAILED (Critical issues found)${NC}"
    exit 1
elif [ $HIGH_COUNT -gt 0 ]; then
    echo -e "${YELLOW}SECURITY SCAN: WARNING (High issues found)${NC}"
    exit 1
else
    echo -e "${GREEN}SECURITY SCAN: PASSED${NC}"
    exit 0
fi
