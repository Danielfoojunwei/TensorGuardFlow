#!/bin/bash
#
# TensorGuardFlow Empirical Benchmark Runner
#
# This script runs reproducible benchmarks using real public datasets.
# NO simulations. NO mock data. All results are empirically measured.
#
# Usage:
#   ./scripts/bench/run_empirical.sh           # Run all benchmarks with 3 seeds
#   ./scripts/bench/run_empirical.sh --fast    # Quick run for development
#   ./scripts/bench/run_empirical.sh --suite clvision  # Run only CL benchmarks
#
# Outputs:
#   reports/run_manifest.json     - Environment and run configuration
#   reports/metrics.json          - Aggregated metrics
#   reports/benchmark_results.csv - Tabular results
#   reports/benchmark_report.md   - Human-readable report
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TensorGuardFlow Empirical Benchmarks${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Default configuration
SUITE="all"
SEEDS="42 123 456"
OUTPUT_DIR="reports"
DEVICE="auto"
FAIL_ON_MOCK="true"
FAST_MODE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --suite)
            SUITE="$2"
            shift 2
            ;;
        --seeds)
            SEEDS="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --fast)
            FAST_MODE="--fast"
            SEEDS="42"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --suite SUITE    Benchmark suite: clvision, wilds, peft, all (default: all)"
            echo "  --seeds SEEDS    Random seeds (default: 42 123 456)"
            echo "  --output DIR     Output directory (default: reports)"
            echo "  --device DEV     Device: cuda, cpu, auto (default: auto)"
            echo "  --fast           Fast mode for quick testing"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo "Configuration:"
echo "  Suite:       ${SUITE}"
echo "  Seeds:       ${SEEDS}"
echo "  Output:      ${OUTPUT_DIR}"
echo "  Device:      ${DEVICE}"
echo "  Fail on mock: ${FAIL_ON_MOCK}"
if [ -n "$FAST_MODE" ]; then
    echo -e "  ${YELLOW}FAST MODE ENABLED${NC}"
fi
echo ""

# Check Python and dependencies
echo "Checking environment..."
if ! command -v python &> /dev/null; then
    echo -e "${RED}Error: Python not found${NC}"
    exit 1
fi

# Check if torch is installed
if ! python -c "import torch" 2>/dev/null; then
    echo -e "${YELLOW}Warning: PyTorch not installed. Installing...${NC}"
    pip install torch torchvision
fi

# Check if benchmarks_empirical is available
if ! python -c "import benchmarks_empirical" 2>/dev/null; then
    echo -e "${YELLOW}Installing benchmarks_empirical...${NC}"
    cd "$(dirname "$0")/../.."
    pip install -e ".[bench]" || pip install -e .
fi

echo ""
echo -e "${GREEN}Starting benchmarks...${NC}"
echo ""

# Create output directory
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/raw"

# Run the benchmark
python -m benchmarks_empirical.run \
    --suite "${SUITE}" \
    --seeds ${SEEDS} \
    --output_dir "${OUTPUT_DIR}" \
    --device "${DEVICE}" \
    --fail_on_mock "${FAIL_ON_MOCK}" \
    ${FAST_MODE}

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}BENCHMARK COMPLETE - SUCCESS${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Outputs generated:"
    ls -la "${OUTPUT_DIR}"/*.json "${OUTPUT_DIR}"/*.csv "${OUTPUT_DIR}"/*.md 2>/dev/null || true
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}BENCHMARK FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi

echo ""
echo "View the report:"
echo "  cat ${OUTPUT_DIR}/benchmark_report.md"
