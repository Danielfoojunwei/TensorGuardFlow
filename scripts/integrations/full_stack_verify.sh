#!/bin/bash
#
# TensorGuardFlow Full-Stack Integration Verification Script
#
# This script runs all integration tests in sequence and generates a proof pack.
#
# Usage:
#   ./scripts/integrations/full_stack_verify.sh [options]
#
# Options:
#   --tier1-only      Run only contract schema tests (no cloud required)
#   --tier2-only      Run only local E2E tests
#   --tier3-only      Run only provider smoke tests (requires credentials)
#   --skip-tier3      Skip provider smoke tests even if credentials available
#   --output-dir DIR  Directory for proof pack output (default: reports/integrations)
#   --verbose         Enable verbose output
#   --fail-fast       Stop on first failure
#   --help            Show this help message
#
# Exit codes:
#   0  All tests passed
#   1  One or more tests failed
#   2  Setup/configuration error

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
OUTPUT_DIR="reports/integrations"
VERBOSE=false
FAIL_FAST=false
RUN_TIER1=true
RUN_TIER2=true
RUN_TIER3=true
SKIP_TIER3=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tier1-only)
            RUN_TIER1=true
            RUN_TIER2=false
            RUN_TIER3=false
            shift
            ;;
        --tier2-only)
            RUN_TIER1=false
            RUN_TIER2=true
            RUN_TIER3=false
            shift
            ;;
        --tier3-only)
            RUN_TIER1=false
            RUN_TIER2=false
            RUN_TIER3=true
            shift
            ;;
        --skip-tier3)
            SKIP_TIER3=true
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --fail-fast)
            FAIL_FAST=true
            shift
            ;;
        --help)
            head -30 "$0" | grep -E '^#' | tail -n +3 | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 2
            ;;
    esac
done

# Create output directory
RUN_ID=$(date +%Y%m%d_%H%M%S)
RUN_DIR="${OUTPUT_DIR}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

echo "=============================================="
echo "TensorGuardFlow Full-Stack Integration Verify"
echo "=============================================="
echo ""
echo "Run ID: ${RUN_ID}"
echo "Output: ${RUN_DIR}"
echo ""

# Initialize results tracking
TIER1_RESULT="skipped"
TIER2_RESULT="skipped"
TIER3_RESULT="skipped"
OVERALL_RESULT="passed"

# Helper function for test execution
run_tests() {
    local tier_name=$1
    local test_pattern=$2
    local output_file=$3

    echo -e "${BLUE}>>> Running ${tier_name}...${NC}"

    local pytest_args="-v --tb=short --junitxml=${RUN_DIR}/${output_file}"

    if [ "$VERBOSE" = true ]; then
        pytest_args="${pytest_args} -s"
    fi

    if [ "$FAIL_FAST" = true ]; then
        pytest_args="${pytest_args} -x"
    fi

    if PYTHONPATH=src python -m pytest ${test_pattern} ${pytest_args} 2>&1 | tee "${RUN_DIR}/${tier_name}.log"; then
        echo -e "${GREEN}>>> ${tier_name}: PASSED${NC}"
        return 0
    else
        echo -e "${RED}>>> ${tier_name}: FAILED${NC}"
        return 1
    fi
}

# TIER 1: Contract Schema Tests
if [ "$RUN_TIER1" = true ]; then
    echo ""
    echo "=========================================="
    echo "TIER 1: Contract Schema Tests"
    echo "=========================================="
    echo "Validating all exporter output schemas..."
    echo ""

    if run_tests "tier1_contracts" "tests/integration/full_stack/test_contract_schemas.py" "junit_tier1.xml"; then
        TIER1_RESULT="passed"
    else
        TIER1_RESULT="failed"
        OVERALL_RESULT="failed"
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping due to --fail-fast${NC}"
            exit 1
        fi
    fi
fi

# TIER 2: Local E2E Tests
if [ "$RUN_TIER2" = true ]; then
    echo ""
    echo "=========================================="
    echo "TIER 2: Local E2E Tests"
    echo "=========================================="
    echo "Running local integration cycle..."
    echo ""

    if run_tests "tier2_local_e2e" "tests/integration/full_stack/test_local_e2e.py" "junit_tier2.xml"; then
        TIER2_RESULT="passed"
    else
        TIER2_RESULT="failed"
        OVERALL_RESULT="failed"
        if [ "$FAIL_FAST" = true ]; then
            echo -e "${RED}Stopping due to --fail-fast${NC}"
            exit 1
        fi
    fi
fi

# TIER 3: Provider Smoke Tests (optional)
if [ "$RUN_TIER3" = true ] && [ "$SKIP_TIER3" = false ]; then
    echo ""
    echo "=========================================="
    echo "TIER 3: Provider Smoke Tests"
    echo "=========================================="
    echo "Running provider connectivity tests..."
    echo "(Tests will be skipped if credentials not available)"
    echo ""

    # Check for any credentials
    HAS_ANY_CREDS=false
    [ -n "$AWS_ACCESS_KEY_ID" ] && HAS_ANY_CREDS=true
    [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && HAS_ANY_CREDS=true
    [ -n "$AZURE_SUBSCRIPTION_ID" ] && HAS_ANY_CREDS=true
    [ -n "$DATABRICKS_HOST" ] && HAS_ANY_CREDS=true

    if [ "$HAS_ANY_CREDS" = true ] || [ -f ~/.aws/credentials ]; then
        if run_tests "tier3_provider_smoke" "tests/integration/full_stack/test_provider_smoke.py" "junit_tier3.xml"; then
            TIER3_RESULT="passed"
        else
            # Provider smoke failures are warnings, not hard failures
            TIER3_RESULT="warning"
            echo -e "${YELLOW}>>> Provider smoke tests had failures (non-blocking)${NC}"
        fi
    else
        echo -e "${YELLOW}>>> No cloud credentials found, skipping TIER 3${NC}"
        TIER3_RESULT="skipped"
    fi
fi

# Generate topology snapshot
echo ""
echo "=========================================="
echo "Generating Integration Topology Snapshot"
echo "=========================================="

PYTHONPATH=src python << 'EOF' > "${RUN_DIR}/topology.json"
import json
from datetime import datetime
from tensorguard.integrations.framework.manager import IntegrationManager
from tensorguard.integrations.framework.topology import TopologyBuilder

# Build sample topology for verification
builder = TopologyBuilder()

# Add standard local nodes
builder.add_node("local_data", "local_filesystem", "data_source", "healthy")
builder.add_node("local_training", "local_gpu", "training", "healthy")
builder.add_node("internal_tracking", "tgf_internal", "tracking", "healthy")
builder.add_node("local_signing", "local_dev", "trust", "healthy")

# Add edges
builder.add_edge("local_data", "local_training", "feeds")
builder.add_edge("local_training", "internal_tracking", "reports_to")

topology = builder.build()

output = {
    "generated_at": datetime.utcnow().isoformat(),
    "topology": topology.to_dict(),
    "summary": {
        "total_nodes": len(topology.nodes),
        "total_edges": len(topology.edges),
        "categories": list(set(n.category for n in topology.nodes)),
    }
}

print(json.dumps(output, indent=2))
EOF

echo "Topology saved to ${RUN_DIR}/topology.json"

# Generate export samples
echo ""
echo "=========================================="
echo "Generating Sample Export Artifacts"
echo "=========================================="

mkdir -p "${RUN_DIR}/exports"

PYTHONPATH=src python << 'EOF'
import json
import os

from tensorguard.integrations.exporters import (
    VLLMExporter,
    TGIExporter,
    SageMakerExporter,
    VertexAIExporter,
)

run_dir = os.environ.get("RUN_DIR", "reports/integrations/sample")
exports_dir = f"{run_dir}/exports"

context = {
    "route_key": "verification_route",
    "adapter_id": "adapter_v1",
    "adapter_uri": "s3://tgf-adapters/verification/adapter.safetensors",
    "run_id": "verification_run",
}

# vLLM export
vllm = VLLMExporter({
    "base_model": "meta-llama/Llama-2-7b-hf",
    "tensor_parallel_size": 1,
})
for artifact in vllm.export(context):
    with open(f"{exports_dir}/vllm_{artifact.name}", "w") as f:
        f.write(artifact.content)

# TGI export
tgi = TGIExporter({
    "base_model": "meta-llama/Llama-2-7b-hf",
})
for artifact in tgi.export(context):
    with open(f"{exports_dir}/tgi_{artifact.name}", "w") as f:
        f.write(artifact.content)

print(f"Sample exports saved to {exports_dir}/")
EOF

export RUN_DIR="${RUN_DIR}"
PYTHONPATH=src python << 'EOF'
import json
import os

from tensorguard.integrations.exporters import (
    VLLMExporter,
    TGIExporter,
)

run_dir = os.environ.get("RUN_DIR", "reports/integrations/sample")
exports_dir = f"{run_dir}/exports"

context = {
    "route_key": "verification_route",
    "adapter_id": "adapter_v1",
    "adapter_uri": "s3://tgf-adapters/verification/adapter.safetensors",
    "run_id": "verification_run",
}

# vLLM export
vllm = VLLMExporter({
    "base_model": "meta-llama/Llama-2-7b-hf",
    "tensor_parallel_size": 1,
})
for artifact in vllm.export(context):
    with open(f"{exports_dir}/vllm_{artifact.name}", "w") as f:
        f.write(artifact.content)

# TGI export
tgi = TGIExporter({
    "base_model": "meta-llama/Llama-2-7b-hf",
})
for artifact in tgi.export(context):
    with open(f"{exports_dir}/tgi_{artifact.name}", "w") as f:
        f.write(artifact.content)

print(f"Sample exports saved to {exports_dir}/")
EOF

echo "Sample exports saved to ${RUN_DIR}/exports/"

# Generate proof pack manifest
echo ""
echo "=========================================="
echo "Generating Proof Pack Manifest"
echo "=========================================="

cat > "${RUN_DIR}/manifest.json" << EOF
{
    "run_id": "${RUN_ID}",
    "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "results": {
        "tier1_contracts": "${TIER1_RESULT}",
        "tier2_local_e2e": "${TIER2_RESULT}",
        "tier3_provider_smoke": "${TIER3_RESULT}",
        "overall": "${OVERALL_RESULT}"
    },
    "artifacts": {
        "topology": "topology.json",
        "exports": "exports/",
        "junit_reports": [
            "junit_tier1.xml",
            "junit_tier2.xml",
            "junit_tier3.xml"
        ],
        "logs": [
            "tier1_contracts.log",
            "tier2_local_e2e.log",
            "tier3_provider_smoke.log"
        ]
    },
    "environment": {
        "python_version": "$(python --version 2>&1)",
        "platform": "$(uname -s)",
        "tg_environment": "${TG_ENVIRONMENT:-development}",
        "tg_enable_remote_submit": "${TG_ENABLE_REMOTE_SUBMIT:-false}"
    }
}
EOF

echo "Manifest saved to ${RUN_DIR}/manifest.json"

# Print summary
echo ""
echo "=============================================="
echo "VERIFICATION SUMMARY"
echo "=============================================="
echo ""
echo "Run ID: ${RUN_ID}"
echo ""
echo "Results:"
echo -e "  TIER 1 (Contract Schemas): ${TIER1_RESULT}"
echo -e "  TIER 2 (Local E2E):        ${TIER2_RESULT}"
echo -e "  TIER 3 (Provider Smoke):   ${TIER3_RESULT}"
echo ""

if [ "$OVERALL_RESULT" = "passed" ]; then
    echo -e "${GREEN}OVERALL: PASSED${NC}"
    echo ""
    echo "Proof pack generated at: ${RUN_DIR}/"
    echo ""
    echo "Contents:"
    ls -la "${RUN_DIR}/"
    exit 0
else
    echo -e "${RED}OVERALL: FAILED${NC}"
    echo ""
    echo "Check logs in: ${RUN_DIR}/"
    exit 1
fi
