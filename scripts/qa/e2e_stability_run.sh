#!/usr/bin/env bash
# E2E Stability Run Script
# Runs E2E tests twice to detect flaky tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Output directory
OUTPUT_DIR="${1:-$PROJECT_ROOT/artifacts/qa/e2e_stability/$TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "E2E Stability Run - TensorGuardFlow"
echo "=============================================="
echo "Output Directory: $OUTPUT_DIR"
echo ""

# Function to run E2E tests
run_e2e() {
    local run_number=$1
    local output_file="$OUTPUT_DIR/run_${run_number}.log"
    local junit_file="$OUTPUT_DIR/junit_run_${run_number}.xml"

    echo "--- Run $run_number Starting ---"

    cd "$FRONTEND_DIR"

    # Check if playwright is installed
    if ! npx playwright --version &>/dev/null; then
        echo "Installing Playwright..."
        npm install -D @playwright/test
        npx playwright install chromium
    fi

    # Run tests
    if BASE_URL="${BASE_URL:-http://localhost:8000}" npx playwright test \
        --reporter=junit \
        --output "$junit_file" \
        2>&1 | tee "$output_file"; then
        echo "--- Run $run_number: PASSED ---"
        return 0
    else
        echo "--- Run $run_number: FAILED ---"
        return 1
    fi
}

# Track results
RUN1_RESULT=0
RUN2_RESULT=0

# Run 1
echo ""
echo "=== Starting Run 1 of 2 ==="
if run_e2e 1; then
    RUN1_RESULT=0
else
    RUN1_RESULT=1
fi

# Run 2
echo ""
echo "=== Starting Run 2 of 2 ==="
if run_e2e 2; then
    RUN2_RESULT=0
else
    RUN2_RESULT=1
fi

# Generate summary
echo ""
echo "=============================================="
echo "E2E Stability Summary"
echo "=============================================="

cat > "$OUTPUT_DIR/stability_summary.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "run_1_passed": $([ $RUN1_RESULT -eq 0 ] && echo "true" || echo "false"),
    "run_2_passed": $([ $RUN2_RESULT -eq 0 ] && echo "true" || echo "false"),
    "both_passed": $([ $RUN1_RESULT -eq 0 ] && [ $RUN2_RESULT -eq 0 ] && echo "true" || echo "false"),
    "flaky_detected": $([ $RUN1_RESULT -ne $RUN2_RESULT ] && echo "true" || echo "false")
}
EOF

echo "Run 1: $([ $RUN1_RESULT -eq 0 ] && echo "PASSED" || echo "FAILED")"
echo "Run 2: $([ $RUN2_RESULT -eq 0 ] && echo "PASSED" || echo "FAILED")"
echo ""

# Determine overall result
if [ $RUN1_RESULT -eq 0 ] && [ $RUN2_RESULT -eq 0 ]; then
    echo "STABILITY CHECK: PASSED (Both runs succeeded)"
    echo "No flaky tests detected."
    exit 0
elif [ $RUN1_RESULT -ne $RUN2_RESULT ]; then
    echo "STABILITY CHECK: FAILED (Flaky tests detected)"
    echo "One run passed and one failed - investigate flaky tests!"
    exit 1
else
    echo "STABILITY CHECK: FAILED (Both runs failed)"
    echo "Tests are consistently failing - fix before release."
    exit 1
fi
