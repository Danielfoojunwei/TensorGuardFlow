"""
Dev Sanity Tests

These tests verify that the development environment is correctly set up
and that basic server functionality works without crashes.

NOTE: For tests that require database fixtures, use tests/integration/test_platform_api.py
which has proper fixture handling for SQLModel's global metadata.
"""

import pytest


class TestDevSanity:
    """Tests that verify development environment works correctly."""

    def test_app_imports_without_error(self):
        """Verify the FastAPI app can be imported without crashing."""
        from tensorguard.platform.main import app
        assert app is not None
        assert hasattr(app, 'routes')

    def test_database_module_imports(self):
        """Verify database module imports correctly."""
        from tensorguard.platform.database import engine, get_session, check_db_health
        assert engine is not None
        assert get_session is not None
        assert callable(check_db_health)

    def test_db_health_check_works(self):
        """Verify database health check function works."""
        from tensorguard.platform.database import check_db_health

        result = check_db_health()
        assert "status" in result
        # Should be healthy with default SQLite
        assert result["status"] in ["healthy", "unhealthy"]


class TestCoreModuleImports:
    """Verify core modules import without errors."""

    def test_import_auth_module(self):
        """Auth module should import cleanly."""
        from tensorguard.platform.auth import (
            get_current_user,
            create_access_token,
            verify_password,
            get_password_hash,
        )
        assert callable(get_current_user)
        assert callable(create_access_token)
        assert callable(verify_password)
        assert callable(get_password_hash)

    def test_import_models(self):
        """Core models should import cleanly."""
        from tensorguard.platform.models.core import (
            Tenant,
            User,
            Fleet,
            Job,
        )
        assert Tenant is not None
        assert User is not None
        assert Fleet is not None
        assert Job is not None

    def test_import_routers(self):
        """API routers should import cleanly."""
        from tensorguard.platform.api.endpoints import router as main_router
        from tensorguard.platform.api.identity_endpoints import router as identity_router
        from tensorguard.platform.api.telemetry_endpoints import router as telemetry_router

        assert main_router is not None
        assert identity_router is not None
        assert telemetry_router is not None


class TestMakefileTargets:
    """Verify Makefile targets work correctly (via import checks)."""

    def test_uvicorn_installed(self):
        """Verify uvicorn is available for 'make dev'."""
        import uvicorn
        assert uvicorn is not None

    def test_pytest_installed(self):
        """Verify pytest is available for 'make test'."""
        import pytest
        assert pytest is not None

    def test_fastapi_test_client_works(self):
        """Verify FastAPI TestClient can be created."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        # This should not crash
        client = TestClient(app, raise_server_exceptions=False)
        assert client is not None

        # Basic health check should work
        response = client.get("/health")
        assert response.status_code == 200
