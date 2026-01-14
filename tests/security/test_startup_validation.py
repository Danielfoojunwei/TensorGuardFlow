import os
import pytest

from tensorguard.utils.startup_validation import validate_startup_config, StartupValidationError


def test_startup_validation_requires_secrets_and_db(monkeypatch):
    monkeypatch.setenv("TG_ENVIRONMENT", "production")
    monkeypatch.delenv("TG_SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TG_DEMO_MODE", raising=False)
    monkeypatch.delenv("TG_ENABLE_AGGREGATION", raising=False)
    monkeypatch.delenv("TG_ENABLE_PQC", raising=False)

    with pytest.raises(StartupValidationError) as excinfo:
        validate_startup_config()

    message = str(excinfo.value)
    assert "TG_SECRET_KEY" in message
    assert "DATABASE_URL" in message


def test_startup_validation_blocks_demo_mode_and_missing_flwr(monkeypatch):
    monkeypatch.setenv("TG_ENVIRONMENT", "production")
    monkeypatch.setenv("TG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("TG_DEMO_MODE", "true")
    monkeypatch.setenv("TG_ENABLE_AGGREGATION", "true")

    with pytest.raises(StartupValidationError) as excinfo:
        validate_startup_config()

    message = str(excinfo.value)
    assert "TG_DEMO_MODE" in message
    assert "Flower aggregation runtime" in message
