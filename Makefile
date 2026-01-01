# Makefile for TensorGuardFlow
# Automation for build, test, and security verification

.PHONY: install test agent bench clean reports lint setup

# Default target
all: test

# Installation
install:
	pip install -e .
	pip install pytest pytest-asyncio tenseal numpy cryptography fastapi sqlmodel uvicorn pydantic-settings xgboost scikit-learn scipy

# Project Setup
setup:
	mkdir -p keys/identity keys/inference keys/aggregation artifacts
	python scripts/setup_env.py

# Testing
test:
	@echo "--- Running Holistic Security Fabric Tests ---"
	export PYTHONPATH=src && python -m pytest tests/

# Agent Orchestration
agent:
	@echo "--- Starting TensorGuard Unified Agent ---"
	export PYTHONPATH=src && python -m tensorguard.agent.daemon

# Benchmarking Subsystem
bench:
	@echo "--- Running TensorGuard Microbenchmarks ---"
	export PYTHONPATH=src && python -m tensorguard.bench.cli micro
	@echo "--- Running Privacy Eval ---"
	export PYTHONPATH=src && python -m tensorguard.bench.cli privacy
	@echo "--- Generating Benchmarking Report ---"
	export PYTHONPATH=src && python -m tensorguard.bench.cli report

# Linting
lint:
	@echo "--- Running Linter (ruff) ---"
	ruff check src/

# Cleanup
clean:
	@echo "--- Cleaning temporary files ---"
	rm -rf .pytest_cache
	rm -rf artifacts/metrics artifacts/privacy artifacts/robustness artifacts/evidence_pack
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f artifacts/report.html
