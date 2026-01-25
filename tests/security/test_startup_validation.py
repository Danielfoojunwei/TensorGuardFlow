import os
import pytest

from tensorguard.utils.production_gates import ProductionGateError, is_production
from tensorguard.utils.startup_validation import validate_startup_config


def test_startup_validation_requires_secret_key_in_production(monkeypatch):
    monkeypatch.setenv("TG_ENVIRONMENT", "production")
    monkeypatch.delenv("TG_SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("TG_KEY_MASTER", "a" * 64)
    is_production.cache_clear()

    import tensorguard.utils.production_gates as pg
    
    with pytest.raises(pg.ProductionGateError):
        validate_startup_config("platform", require_secret_key=True, require_database=True, require_key_master=True)


def test_startup_validation_allows_dev_without_secrets(monkeypatch):
    from unittest.mock import patch
    # Force is_production to False to ensure gates are skipped/warn-only
    with patch("tensorguard.utils.production_gates.is_production", return_value=False):
        monkeypatch.delenv("TG_SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("TG_KEY_MASTER", raising=False)
        
        validate_startup_config("platform", require_secret_key=True, require_database=True, require_key_master=True)
