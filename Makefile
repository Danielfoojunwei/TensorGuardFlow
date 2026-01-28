# Makefile for TensorGuardFlow
# Automation for build, test, development, and deployment

.PHONY: install test agent bench clean lint setup ci typecheck dev dev-backend dev-frontend db-init worker docker docker-prod db-migrate help test-backend test-frontend test-e2e test-integration test-security qa qa-quick full-stack-verify test-full-stack robotics-verify test-robotics-contracts test-robotics-integration test-robotics-smoke test-robotics-ui

# Default target
all: help

# ============================================================================
# HELP
# ============================================================================
help:
	@echo "TensorGuardFlow Development Commands"
	@echo "====================================="
	@echo ""
	@echo "Quick Start:"
	@echo "  make install    - Install all dependencies"
	@echo "  make dev        - Start backend + frontend for development"
	@echo "  make test       - Run all tests"
	@echo ""
	@echo "Development:"
	@echo "  make dev-backend   - Start backend server only (port 8000)"
	@echo "  make dev-frontend  - Start frontend dev server only (port 5173)"
	@echo "  make db-init       - Initialize database with tables"
	@echo ""
	@echo "Quality:"
	@echo "  make lint       - Run linter (ruff)"
	@echo "  make typecheck  - Run type checker (mypy)"
	@echo "  make ci         - Run full CI pipeline"
	@echo ""
	@echo "Production:"
	@echo "  make server     - Start production server"
	@echo "  make worker     - Start background worker (identity renewal, etc)"
	@echo "  make agent      - Start unified agent daemon"
	@echo ""
	@echo "Docker:"
	@echo "  make docker     - Start with docker compose (dev mode)"
	@echo "  make docker-prod - Start with docker compose (production)"
	@echo "  make db-migrate  - Run database migrations (alembic)"
	@echo ""
	@echo "Benchmarking (Empirical - Real Datasets):"
	@echo "  make bench         - Run all empirical benchmarks (3 seeds, real data)"
	@echo "  make bench-cl      - Continual Learning benchmarks only"
	@echo "  make bench-wilds   - WILDS distribution shift benchmarks only"
	@echo "  make bench-peft    - PEFT/LoRA benchmarks only"
	@echo "  make bench-fast    - Quick benchmark (1 seed, reduced epochs)"
	@echo ""
	@echo "Benchmarking (Infrastructure/API):"
	@echo "  make bench-api     - API latency benchmarks"
	@echo "  make bench-ingest  - Telemetry ingest benchmarks"
	@echo "  make bench-smoke   - Quick benchmark smoke test"
	@echo "  make bench-stress  - High-load stress testing"
	@echo "  make bench-regression - Compare against baseline"
	@echo ""
	@echo "Integration Verification:"
	@echo "  make full-stack-verify   - Run all integration tests and generate proof pack"
	@echo "  make test-full-stack     - Run full-stack integration tests only"
	@echo ""
	@echo "Robotics Ops Integrations:"
	@echo "  make robotics-verify          - Run robotics verification and generate proof pack"
	@echo "  make test-robotics-contracts  - Run robotics contract tests (TIER 1)"
	@echo "  make test-robotics-integration - Run robotics integration tests (TIER 2)"
	@echo "  make test-robotics-smoke      - Run robotics smoke tests (TIER 3, requires creds)"
	@echo "  make test-robotics-ui         - Run robotics UI tests (requires Playwright)"
	@echo ""

# ============================================================================
# INSTALLATION
# ============================================================================
install:
	pip install -e ".[all]"

install-core:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-bench:
	pip install -e ".[bench]"

# ============================================================================
# DEVELOPMENT
# ============================================================================

# Start both backend and frontend for local development
dev:
	@echo "=== Starting TensorGuardFlow Development Environment ==="
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173 (if built)"
	@echo "API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "Starting backend server..."
	PYTHONPATH=src python -m uvicorn tensorguard.platform.main:app --host 0.0.0.0 --port 8000 --reload

# Start backend only
dev-backend:
	@echo "--- Starting Backend Server (port 8000) ---"
	PYTHONPATH=src python -m uvicorn tensorguard.platform.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend only (requires npm install in frontend/)
dev-frontend:
	@echo "--- Starting Frontend Dev Server (port 5173) ---"
	cd frontend && npm run dev

# Initialize database tables
db-init:
	@echo "--- Initializing Database ---"
	PYTHONPATH=src python -c "from tensorguard.platform.database import engine; from sqlmodel import SQLModel; SQLModel.metadata.create_all(engine); print('Database initialized successfully')"

# ============================================================================
# PRODUCTION
# ============================================================================

# Start production server
server:
	@echo "--- Starting TensorGuard Platform Server ---"
	PYTHONPATH=src python -m uvicorn tensorguard.platform.main:app --host 0.0.0.0 --port 8000

# Start unified agent daemon
agent:
	@echo "--- Starting TensorGuard Unified Agent ---"
	PYTHONPATH=src python -m tensorguard.agent.daemon

# Start background worker for identity renewal and other jobs
worker:
	@echo "--- Starting TensorGuard Background Worker ---"
	TG_ENVIRONMENT=development PYTHONPATH=src python -m tensorguard.platform.worker

# ============================================================================
# DOCKER
# ============================================================================

# Start with docker compose (development mode, SQLite)
docker:
	@echo "--- Starting TensorGuard with Docker Compose (dev) ---"
	docker compose up --build

# Start with docker compose (production mode, PostgreSQL)
docker-prod:
	@echo "--- Starting TensorGuard with Docker Compose (production) ---"
	docker compose --profile production up --build

# Run database migrations
db-migrate:
	@echo "--- Running Database Migrations ---"
	PYTHONPATH=src alembic upgrade head

# ============================================================================
# TESTING
# ============================================================================
test:
	@echo "--- Running Tests ---"
	PYTHONPATH=src python -m pytest tests/ -v

test-quick:
	@echo "--- Running Quick Tests (no slow markers) ---"
	PYTHONPATH=src python -m pytest tests/ -v -m "not slow"

test-integration:
	@echo "--- Running Integration Tests ---"
	PYTHONPATH=src python -m pytest tests/integration/ -v

# ============================================================================
# CODE QUALITY
# ============================================================================
lint:
	@echo "--- Running Linter (ruff) ---"
	ruff check src/

lint-fix:
	@echo "--- Running Linter with Auto-fix ---"
	ruff check src/ --fix

typecheck:
	@echo "--- Running Type Checker (mypy) ---"
	mypy src/

# CI target: install, lint, tests
ci: install lint test
	@echo "--- CI checks completed ---"

# ============================================================================
# BENCHMARKING
# ============================================================================

# Run internal microbenchmarks (crypto, privacy, etc.)
bench-internal:
	@echo "--- Running TensorGuard Microbenchmarks ---"
	PYTHONPATH=src python -m tensorguard.bench.cli micro
	@echo "--- Running Privacy Eval ---"
	PYTHONPATH=src python -m tensorguard.bench.cli privacy
	@echo "--- Generating Benchmarking Report ---"
	PYTHONPATH=src python -m tensorguard.bench.cli report

# ============================================================================
# EMPIRICAL BENCHMARKS (Real Public Datasets)
# ============================================================================

# Run all empirical benchmarks with 3 seeds (canonical benchmark)
bench:
	@echo "=============================================="
	@echo "TENSORGUARDFLOW EMPIRICAL BENCHMARKS"
	@echo "=============================================="
	@echo "Running benchmarks on real public datasets..."
	@echo "This will download CIFAR-100, TinyImageNet, CORe50, and WILDS datasets."
	@echo ""
	@mkdir -p reports
	python -m benchmarks_empirical.run --suite all --seeds 42 123 456 --output_dir reports --fail_on_mock true
	@echo ""
	@echo "Benchmark complete. Outputs:"
	@echo "  - reports/run_manifest.json"
	@echo "  - reports/metrics.json"
	@echo "  - reports/benchmark_results.csv"
	@echo "  - reports/benchmark_report.md"

# Run only Continual Learning benchmarks
bench-cl:
	@echo "--- Running Continual Learning Benchmarks ---"
	@mkdir -p reports
	python -m benchmarks_empirical.run --suite clvision --seeds 42 123 456 --output_dir reports

# Run only WILDS distribution shift benchmarks
bench-wilds:
	@echo "--- Running WILDS Distribution Shift Benchmarks ---"
	@mkdir -p reports
	python -m benchmarks_empirical.run --suite wilds --seeds 42 123 456 --output_dir reports

# Run only PEFT/LoRA benchmarks
bench-peft:
	@echo "--- Running PEFT/LoRA Benchmarks ---"
	@mkdir -p reports
	python -m benchmarks_empirical.run --suite peft --seeds 42 123 456 --output_dir reports

# Fast benchmark run (1 seed, reduced epochs) for development
bench-fast:
	@echo "--- Running Fast Benchmarks (Development Mode) ---"
	@mkdir -p reports
	python -m benchmarks_empirical.run --suite all --fast --output_dir reports

# Run benchmarks using shell script
bench-script:
	@./scripts/bench/run_empirical.sh

# ============================================================================
# LEGACY API BENCHMARKS (Infrastructure Testing)
# ============================================================================

# Run API performance benchmarks
bench-api:
	@echo "--- Running API Latency Benchmarks ---"
	@mkdir -p artifacts/benchmarks
	python -m benchmarks.runner api --scenario standard --output-dir artifacts/benchmarks

# Telemetry ingest throughput benchmarks
bench-ingest:
	@echo "--- Running Telemetry Ingest Benchmarks ---"
	@mkdir -p artifacts/benchmarks
	python -m benchmarks.runner ingest --scenario standard --output-dir artifacts/benchmarks

# Quick smoke test for benchmarks
bench-smoke:
	@echo "--- Running Benchmark Smoke Tests ---"
	python -m benchmarks.runner all --scenario smoke --output-dir artifacts/benchmarks

# Stress test (high concurrency, long duration)
bench-stress:
	@echo "--- Running Stress Benchmarks ---"
	python -m benchmarks.runner all --scenario stress --output-dir artifacts/benchmarks

# Validate benchmark infrastructure
bench-validate:
	@echo "--- Validating Benchmark Setup ---"
	python -m benchmarks.runner api --duration 5 --concurrent 2 --warmup 1 --output-dir artifacts/benchmarks

# Performance regression test against baseline
bench-regression:
	@echo "--- Running Performance Regression Test ---"
	python -m benchmarks.regression_test --baseline artifacts/benchmarks/benchmark_baseline_20260120.json --latency-threshold 20 --throughput-threshold 20

# ============================================================================
# QA & RELEASE TESTING
# ============================================================================

# Run full QA harness (generates release readiness report)
qa:
	@echo "--- Running Full QA Harness ---"
	./scripts/qa/run_all.sh

# Run quick QA (skip slow tests, Docker, and performance)
qa-quick:
	@echo "--- Running Quick QA Harness ---"
	./scripts/qa/run_all.sh --quick --skip-docker

# Backend tests with JUnit output
test-backend:
	@echo "--- Running Backend Tests with JUnit Output ---"
	PYTHONPATH=src python -m pytest tests/unit/ tests/integration/ -v --junitxml=artifacts/qa/junit_backend.xml --cov=src/tensorguard --cov-report=xml:artifacts/qa/coverage.xml

# Frontend tests (requires vitest setup)
test-frontend:
	@echo "--- Running Frontend Tests ---"
	cd frontend && npm run test

# E2E tests
test-e2e:
	@echo "--- Running E2E Tests ---"
	PYTHONPATH=src python -m pytest tests/e2e/ -v --junitxml=artifacts/qa/junit_e2e.xml

# Security tests
test-security:
	@echo "--- Running Security Tests ---"
	PYTHONPATH=src python -m pytest tests/security/ -v --junitxml=artifacts/qa/junit_security.xml

# ============================================================================
# SETUP & CLEANUP
# ============================================================================
setup:
	mkdir -p keys/identity keys/inference keys/aggregation artifacts data artifacts/qa
	@echo "--- Directory structure created ---"

clean:
	@echo "--- Cleaning temporary files ---"
	rm -rf .pytest_cache
	rm -rf artifacts/metrics artifacts/privacy artifacts/robustness artifacts/evidence_pack
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f artifacts/report.html
	rm -f tg_platform.db

# ============================================================================
# INTEGRATION VERIFICATION
# ============================================================================

# Run full-stack integration verification and generate proof pack
full-stack-verify:
	@echo "--- Running Full-Stack Integration Verification ---"
	@mkdir -p reports/integrations
	./scripts/integrations/full_stack_verify.sh

# Run full-stack integration tests only (without proof pack generation)
test-full-stack:
	@echo "--- Running Full-Stack Integration Tests ---"
	PYTHONPATH=src python -m pytest tests/integration/full_stack/ -v

# Run only contract schema tests (TIER 1)
test-full-stack-contracts:
	@echo "--- Running Contract Schema Tests (TIER 1) ---"
	PYTHONPATH=src python -m pytest tests/integration/full_stack/test_contract_schemas.py -v

# Run only local E2E tests (TIER 2)
test-full-stack-e2e:
	@echo "--- Running Local E2E Tests (TIER 2) ---"
	PYTHONPATH=src python -m pytest tests/integration/full_stack/test_local_e2e.py -v

# Run provider smoke tests (TIER 3, requires credentials)
test-full-stack-providers:
	@echo "--- Running Provider Smoke Tests (TIER 3) ---"
	PYTHONPATH=src python -m pytest tests/integration/full_stack/test_provider_smoke.py -v

# ============================================================================
# ROBOTICS OPS INTEGRATIONS
# ============================================================================

# Run robotics ops integrations verification and generate proof pack
robotics-verify:
	@echo "--- Running Robotics Ops Integrations Verification ---"
	@mkdir -p reports/robotics_integrations
	./scripts/integrations/robotics_verify.sh

# Run robotics contract tests only (TIER 1)
test-robotics-contracts:
	@echo "--- Running Robotics Contract Tests (TIER 1) ---"
	PYTHONPATH=src python -m pytest tests/contract/robotics_integrations/ -v

# Run robotics integration tests only (TIER 2)
test-robotics-integration:
	@echo "--- Running Robotics Integration Tests (TIER 2) ---"
	PYTHONPATH=src python -m pytest tests/integration/robotics_ops_loop/ -v

# Run robotics smoke tests (TIER 3, requires credentials)
test-robotics-smoke:
	@echo "--- Running Robotics Smoke Tests (TIER 3) ---"
	./scripts/integrations/robotics_verify.sh --smoke

# Run robotics UI tests (requires Playwright)
test-robotics-ui:
	@echo "--- Running Robotics UI Tests ---"
	cd frontend && npx playwright test tests/ui/robotics_integrations_console.spec.ts
