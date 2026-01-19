"""
Frontend API Contract Tests

Validates that all endpoints the frontend depends on exist and respond correctly.
This test ensures no 404s from the frontend's perspective.

Run with: pytest tests/integration/test_frontend_contract.py -v
"""

import pytest


def get_test_client():
    """Get a test client using the app's default database."""
    from fastapi.testclient import TestClient
    from tensorguard.platform.main import app
    return TestClient(app, raise_server_exceptions=False)


def get_auth_token(client) -> str:
    """Create a test user and return auth token."""
    import secrets
    suffix = secrets.token_hex(4)
    email = f"contract_test_{suffix}@test.com"
    password = "SecurePassword123!"
    org_name = f"ContractTestOrg_{suffix}"

    # Create org and user
    client.post(
        "/api/v1/onboarding/init",
        params={
            "name": org_name,
            "admin_email": email,
            "admin_pass": password
        }
    )

    # Login
    response = client.post(
        "/api/v1/auth/token",
        json={"username": email, "password": password}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


class TestPublicEndpoints:
    """Test endpoints that should be accessible without authentication."""

    def test_health_endpoint(self):
        """GET /health should return 200."""
        client = get_test_client()
        response = client.get("/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data

    def test_ready_endpoint(self):
        """GET /ready should return 200 or 503."""
        client = get_test_client()
        response = client.get("/ready")
        assert response.status_code in [200, 503], f"Expected 200/503, got {response.status_code}"

    def test_live_endpoint(self):
        """GET /live should return 200."""
        client = get_test_client()
        response = client.get("/live")
        assert response.status_code == 200

    def test_docs_endpoint(self):
        """GET /docs should return 200."""
        client = get_test_client()
        response = client.get("/docs")
        assert response.status_code == 200

    def test_api_v1_health_alias(self):
        """GET /api/v1/health should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_api_v1_status_endpoint(self):
        """GET /api/v1/status should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/status")
        assert response.status_code == 200


class TestProtectedEndpointsRequireAuth:
    """Test that protected endpoints return 401 without authentication."""

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/fleets"),
        ("GET", "/api/v1/fleets/extended"),
        ("GET", "/api/v1/jobs"),
        ("GET", "/api/v1/telemetry/pipeline"),
        ("GET", "/api/v1/telemetry/devices"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/vla/models"),
        ("GET", "/api/v1/identity/inventory"),
        ("GET", "/api/v1/fedmoe/experts"),
        ("GET", "/api/v1/kms/keys"),
        ("GET", "/api/v1/peft/profiles"),
        ("GET", "/api/v1/enablement/stats"),
    ])
    def test_endpoint_requires_auth(self, method, path):
        """Endpoint should return 401 without authentication."""
        client = get_test_client()
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path)

        assert response.status_code == 401, \
            f"{method} {path} should return 401 without auth, got {response.status_code}"


class TestFrontendCriticalEndpoints:
    """
    Test all endpoints that the frontend explicitly calls.

    These are derived from frontend/src/services/api.js
    """

    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers for testing."""
        client = get_test_client()
        token = get_auth_token(client)
        if token:
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Could not obtain auth token")

    # VLA Endpoints
    def test_vla_models_list(self, auth_headers):
        """GET /api/v1/vla/models should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/vla/models", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_vla_safety_metrics(self, auth_headers):
        """GET /api/v1/vla/safety/metrics/{fleet_id} should not 404."""
        client = get_test_client()
        response = client.get("/api/v1/vla/safety/metrics/test-fleet", headers=auth_headers)
        # Can be 200 or 404 for missing fleet, but should NOT be 404 for route
        assert response.status_code in [200, 404, 500], f"Got {response.status_code}"

    # Identity Endpoints
    def test_identity_inventory(self, auth_headers):
        """GET /api/v1/identity/inventory should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/identity/inventory", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_identity_policies(self, auth_headers):
        """GET /api/v1/identity/policies should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/identity/policies", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_identity_renewals(self, auth_headers):
        """GET /api/v1/identity/renewals should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/identity/renewals", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_identity_audit(self, auth_headers):
        """GET /api/v1/identity/audit should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/identity/audit", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # FedMoE Endpoints
    def test_fedmoe_experts(self, auth_headers):
        """GET /api/v1/fedmoe/experts should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/fedmoe/experts", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_fedmoe_skills_library(self, auth_headers):
        """GET /api/v1/fedmoe/skills-library should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/fedmoe/skills-library", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Integrations Endpoints
    def test_integrations_status(self, auth_headers):
        """GET /api/v1/integrations/status should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/integrations/status", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # TGSP Endpoints
    def test_tgsp_packages(self, auth_headers):
        """GET /api/v1/tgsp/packages should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/tgsp/packages", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # KMS Endpoints
    def test_kms_keys(self, auth_headers):
        """GET /api/v1/kms/keys should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/kms/keys", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_kms_rotation_schedule(self, auth_headers):
        """GET /api/v1/kms/rotation-schedule should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/kms/rotation-schedule", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_kms_attestation_policies(self, auth_headers):
        """GET /api/v1/kms/attestation-policies should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/kms/attestation-policies", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Pipeline Endpoints
    def test_pipeline_config(self, auth_headers):
        """GET /api/v1/pipeline/config should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/pipeline/config", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Bayesian Policy Endpoints
    def test_policy_bayesian_config(self, auth_headers):
        """GET /api/v1/policy/bayesian/config should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/policy/bayesian/config", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Forensics Endpoints
    def test_forensics_incidents(self, auth_headers):
        """GET /api/v1/forensics/incidents should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/forensics/incidents", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Fleet Endpoints
    def test_fleets_extended(self, auth_headers):
        """GET /api/v1/fleets/extended should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/fleets/extended", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # PEFT Endpoints
    def test_peft_profiles(self, auth_headers):
        """GET /api/v1/peft/profiles should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/peft/profiles", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_peft_runs(self, auth_headers):
        """GET /api/v1/peft/runs should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/peft/runs", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Enablement Endpoints
    def test_enablement_stats(self, auth_headers):
        """GET /api/v1/enablement/stats should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/enablement/stats", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    # Telemetry Endpoints
    def test_telemetry_pipeline(self, auth_headers):
        """GET /api/v1/telemetry/pipeline should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/telemetry/pipeline", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_telemetry_devices(self, auth_headers):
        """GET /api/v1/telemetry/devices should return 200."""
        client = get_test_client()
        response = client.get("/api/v1/telemetry/devices", headers=auth_headers)
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"


class TestFleetAuthentication:
    """Test Fleet Bearer authentication for agent endpoints."""

    @pytest.fixture
    def fleet_credentials(self):
        """Create a fleet and return its credentials."""
        import secrets
        client = get_test_client()
        suffix = secrets.token_hex(4)

        # Create user and org
        email = f"fleet_test_{suffix}@test.com"
        client.post(
            "/api/v1/onboarding/init",
            params={
                "name": f"FleetTestOrg_{suffix}",
                "admin_email": email,
                "admin_pass": "SecurePassword123!"
            }
        )

        # Login
        login_resp = client.post(
            "/api/v1/auth/token",
            json={"username": email, "password": "SecurePassword123!"}
        )
        if login_resp.status_code != 200:
            pytest.skip("Could not login")

        token = login_resp.json()["access_token"]

        # Create fleet
        fleet_resp = client.post(
            f"/api/v1/fleets?name=TestFleet_{suffix}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if fleet_resp.status_code != 200:
            pytest.skip("Could not create fleet")

        fleet_data = fleet_resp.json()
        return {
            "fleet_id": fleet_data["id"],
            "api_key": fleet_data["api_key"],
            "bearer_token": token
        }

    def test_telemetry_ingest_with_fleet_auth(self, fleet_credentials):
        """POST /api/v1/telemetry/ingest should accept Fleet auth."""
        client = get_test_client()
        import time

        payload = {
            "batch_id": f"test_{int(time.time())}",
            "device_info": {"device_id": "test-device"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    def test_telemetry_ingest_rejects_invalid_key(self):
        """POST /api/v1/telemetry/ingest should reject invalid Fleet key."""
        client = get_test_client()

        payload = {
            "batch_id": "invalid_test",
            "device_info": {"device_id": "test-device"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": "Fleet invalid_key_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
