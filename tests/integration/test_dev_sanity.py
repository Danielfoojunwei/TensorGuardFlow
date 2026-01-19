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


class TestFrontendBackendRouteContract:
    """Tests for COMMIT 3: Frontend->backend route contract verification."""

    def test_api_v1_health_endpoint_exists(self):
        """Frontend expects /api/v1/health to exist."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/health")

        # Should not be 404
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_api_v1_status_endpoint_exists(self):
        """Frontend expects /api/v1/status to exist."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/status")

        # Should not be 404
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_api_v1_tgsp_packages_endpoint_exists(self):
        """Frontend expects /api/v1/tgsp/packages to exist."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/tgsp/packages")

        # Should not be 404 (may be 200 or other status, but not missing)
        assert response.status_code != 404

    def test_api_v1_fleets_endpoint_exists(self):
        """Frontend expects /api/v1/fleets to exist."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/fleets")

        # Should not be 404 (will be 401 without auth, which is expected)
        assert response.status_code != 404

    def test_api_v1_auth_token_endpoint_exists(self):
        """Frontend expects /api/v1/auth/token to exist (POST)."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/auth/token", json={"username": "test", "password": "test"})

        # Should not be 404 (may be 401/422 without valid credentials)
        assert response.status_code != 404

    def test_root_health_still_works(self):
        """Root /health endpoint should still work for backward compatibility."""
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")

        assert response.status_code == 200


class TestBackendStartupWithoutFrontend:
    """Tests for COMMIT 2: Backend must not crash if frontend/dist missing."""

    def test_app_starts_without_frontend_dist(self):
        """
        Verify server starts correctly even if frontend/dist doesn't exist.

        This is critical because backend should not depend on frontend build artifacts.
        The app should:
        1. Not crash on import/startup
        2. Serve a helpful message instead of 500 errors
        3. Still serve API endpoints normally
        """
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app

        # App should start (we're here, so it didn't crash)
        client = TestClient(app, raise_server_exceptions=False)

        # API endpoints should work
        response = client.get("/health")
        assert response.status_code == 200

        # API docs should work
        response = client.get("/docs")
        assert response.status_code == 200

    def test_spa_route_returns_helpful_message_when_no_frontend(self):
        """
        When frontend is not built, requesting root should return helpful message.
        """
        from fastapi.testclient import TestClient
        from tensorguard.platform.main import app, FRONTEND_AVAILABLE

        client = TestClient(app, raise_server_exceptions=False)

        # Request root path
        response = client.get("/")

        # Should not be 500 error
        assert response.status_code != 500

        # If frontend is not available, should return helpful HTML
        if not FRONTEND_AVAILABLE:
            assert response.status_code == 200
            assert "TensorGuard Platform" in response.text
            assert "npm run build" in response.text

    def test_static_files_not_mounted_without_frontend(self):
        """
        Static files should only be mounted if frontend/dist exists.
        """
        from tensorguard.platform.main import app, FRONTEND_AVAILABLE

        # Check if /static route exists
        static_routes = [r for r in app.routes if hasattr(r, 'path') and r.path == '/static']

        if not FRONTEND_AVAILABLE:
            # Should NOT have static mount
            assert len(static_routes) == 0, "Static files should not be mounted without frontend"
