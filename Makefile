# Makefile for TensorGuardFlow
# Automation for build, test, development, and deployment

.PHONY: install test agent bench clean lint setup ci typecheck dev dev-backend dev-frontend db-init help

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
	@echo "  make agent      - Start unified agent daemon"
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
bench:
	@echo "--- Running TensorGuard Microbenchmarks ---"
	PYTHONPATH=src python -m tensorguard.bench.cli micro
	@echo "--- Running Privacy Eval ---"
	PYTHONPATH=src python -m tensorguard.bench.cli privacy
	@echo "--- Generating Benchmarking Report ---"
	PYTHONPATH=src python -m tensorguard.bench.cli report

# ============================================================================
# SETUP & CLEANUP
# ============================================================================
setup:
	mkdir -p keys/identity keys/inference keys/aggregation artifacts data
	@echo "--- Directory structure created ---"

clean:
	@echo "--- Cleaning temporary files ---"
	rm -rf .pytest_cache
	rm -rf artifacts/metrics artifacts/privacy artifacts/robustness artifacts/evidence_pack
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f artifacts/report.html
	rm -f tg_platform.db
