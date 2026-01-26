"""
TensorGuard Test Configuration

This conftest.py ensures:
1. Tests run in development environment by default
2. Optional dependencies are handled gracefully
3. Test categories are properly marked
"""
import os
import sys
from typing import Generator

import pytest

# Set development environment for all tests (unless explicitly overridden)
os.environ.setdefault("TG_ENVIRONMENT", "development")
os.environ.setdefault("TG_DEMO_MODE", "false")


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
    config.addinivalue_line(
        "markers", "otel: marks tests that require OpenTelemetry"
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically skip tests with missing optional dependencies.

    This allows tests to be skipped cleanly without manual importorskip
    in every test file.
    """
    # Map markers to required modules
    marker_to_module = {
        "fl": ["flwr", "tenseal"],
        "pqc": ["liboqs"],
        "bench": ["xgboost", "scipy", "sklearn"],
        "otel": ["opentelemetry"],
    }

    for item in items:
        for marker_name, modules in marker_to_module.items():
            if marker_name in [m.name for m in item.iter_markers()]:
                for module in modules:
                    try:
                        __import__(module.replace("-", "_"))
                    except ImportError:
                        skip_marker = pytest.mark.skip(
                            reason=f"Requires optional dependency: {module}"
                        )
                        item.add_marker(skip_marker)
                        break


# =============================================================================
# FIXTURES FOR OPTIONAL DEPENDENCIES
# =============================================================================


@pytest.fixture
def fl_available():
    """Skip test if Federated Learning dependencies are not available."""
    flwr = pytest.importorskip("flwr", reason="Requires flwr for FL tests")
    return flwr


@pytest.fixture
def pqc_available():
    """Skip test if Post-Quantum Cryptography dependencies are not available."""
    liboqs = pytest.importorskip("liboqs", reason="Requires liboqs for PQC tests")
    return liboqs


@pytest.fixture
def tenseal_available():
    """Skip test if TenSEAL is not available."""
    tenseal = pytest.importorskip("tenseal", reason="Requires tenseal for HE tests")
    return tenseal


@pytest.fixture
def otel_available():
    """Skip test if OpenTelemetry is not available."""
    otel = pytest.importorskip("opentelemetry", reason="Requires opentelemetry for tracing tests")
    return otel


# =============================================================================
# COMMON TEST FIXTURES
# =============================================================================


@pytest.fixture
def test_env() -> Generator[dict, None, None]:
    """
    Fixture that sets up a clean test environment and restores it after.
    """
    original_env = os.environ.copy()

    # Set test defaults
    test_defaults = {
        "TG_ENVIRONMENT": "development",
        "TG_DEMO_MODE": "false",
        "TG_SECRET_KEY": "test-secret-key-for-unit-tests-only",
    }
    os.environ.update(test_defaults)

    yield test_defaults

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def demo_mode_enabled() -> Generator[None, None, None]:
    """
    Fixture that temporarily enables demo mode for tests that require it.
    """
    original = os.environ.get("TG_DEMO_MODE")
    os.environ["TG_DEMO_MODE"] = "true"

    yield

    if original is not None:
        os.environ["TG_DEMO_MODE"] = original
    else:
        os.environ.pop("TG_DEMO_MODE", None)
