"""
TensorGuard Test Configuration

This conftest.py ensures:
1. Tests run in development environment by default
2. Optional dependencies are handled gracefully
"""
import os
import pytest

# Set development environment for all tests (unless explicitly overridden)
os.environ.setdefault("TG_ENVIRONMENT", "development")

# Markers for optional dependency tests
def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line(
        "markers", "optional: marks tests that require optional dependencies"
    )
    config.addinivalue_line(
        "markers", "fl: marks tests that require Federated Learning dependencies (flwr, tenseal)"
    )
    config.addinivalue_line(
        "markers", "pqc: marks tests that require Post-Quantum Cryptography dependencies (liboqs)"
    )
    config.addinivalue_line(
        "markers", "bench: marks tests that require benchmarking dependencies"
    )
    config.addinivalue_line(
        "markers", "perf: marks performance benchmarks"
    )
