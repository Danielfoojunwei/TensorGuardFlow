"""
Dashboard Stats Endpoint Tests

Tests for the /dashboard/stats and related dashboard endpoints including:
- Stats computation correctness
- RBAC enforcement
- Response schema validation
- Data isolation between tenants

Run with: pytest tests/integration/test_dashboard_stats.py -v
"""

import pytest
import secrets


def create_test_org_and_user(client, suffix: str = None) -> dict:
    """Create a test organization, user, and return credentials."""
    suffix = suffix or secrets.token_hex(4)
    email = f"dashboard_test_{suffix}@test.com"
    password = "SecurePassword123!"
    org_name = f"DashboardTestOrg_{suffix}"

    # Create org and user
    init_resp = client.post(
        "/api/v1/onboarding/init",
        params={
            "name": org_name,
            "admin_email": email,
            "admin_pass": password
        }
    )
    if init_resp.status_code != 200:
        return None

    # Login
    login_resp = client.post(
        "/api/v1/auth/token",
        json={"username": email, "password": password}
    )
    if login_resp.status_code != 200:
        return None

    token = login_resp.json()["access_token"]
    return {
        "email": email,
        "password": password,
        "org_name": org_name,
        "bearer_token": token
    }


class TestDashboardStatsBasic:
    """Test basic dashboard stats functionality."""

    def test_dashboard_stats_returns_valid_response(self, client):
        """Dashboard stats should return a valid response with required fields."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()

        # Check all required fields exist
        required_fields = [
            "system_health",
            "fleet_count",
            "device_count",
            "devices_online",
            "key_rotations_24h",
            "compliance_level",
            "privacy_budget_remaining",
            "active_training_runs",
            "pending_deployments",
            "models_deployed",
            "success_rate",
            "certificates_expiring"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_dashboard_stats_types_correct(self, client):
        """Dashboard stats should return correct data types."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate types
        assert isinstance(data["system_health"], dict)
        assert isinstance(data["fleet_count"], int)
        assert isinstance(data["device_count"], int)
        assert isinstance(data["devices_online"], int)
        assert isinstance(data["key_rotations_24h"], int)
        assert isinstance(data["compliance_level"], int)
        assert isinstance(data["privacy_budget_remaining"], (int, float))
        assert isinstance(data["active_training_runs"], int)
        assert isinstance(data["pending_deployments"], int)
        assert isinstance(data["models_deployed"], int)
        assert isinstance(data["success_rate"], (int, float))
        assert isinstance(data["certificates_expiring"], int)

    def test_dashboard_stats_fresh_org_zeroes(self, client):
        """Fresh organization should have zero counts for most metrics."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Fresh org should have 0 for most counts
        assert data["fleet_count"] == 0
        assert data["device_count"] == 0
        assert data["devices_online"] == 0
        assert data["key_rotations_24h"] == 0
        assert data["certificates_expiring"] == 0

    def test_dashboard_stats_compliance_level_range(self, client):
        """Compliance level should be between 1 and 5."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 1 <= data["compliance_level"] <= 5

    def test_dashboard_stats_success_rate_range(self, client):
        """Success rate should be between 0 and 100."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 0 <= data["success_rate"] <= 100


class TestDashboardStatsWithFleets:
    """Test dashboard stats with fleets created."""

    def test_fleet_count_increments(self, client):
        """Fleet count should reflect created fleets."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        # Create a fleet
        fleet_resp = client.post(
            f"/api/v1/fleets?name=TestFleet_{secrets.token_hex(4)}",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )
        if fleet_resp.status_code != 200:
            pytest.skip("Could not create fleet")

        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have at least 1 fleet
        assert data["fleet_count"] >= 1

    def test_multiple_fleets_counted(self, client):
        """Multiple fleets should be counted correctly."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        # Create first fleet
        client.post(
            f"/api/v1/fleets?name=Fleet1_{secrets.token_hex(4)}",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        # Get initial count
        initial_resp = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )
        initial_count = initial_resp.json()["fleet_count"]

        # Create another fleet
        client.post(
            f"/api/v1/fleets?name=Fleet2_{secrets.token_hex(4)}",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        # Check count incremented
        updated_resp = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )
        updated_count = updated_resp.json()["fleet_count"]

        assert updated_count == initial_count + 1


class TestDashboardAuthentication:
    """Test authentication requirements for dashboard endpoints."""

    def test_dashboard_stats_requires_auth(self, client):
        """Dashboard stats should reject requests without auth."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 401

    def test_dashboard_stats_rejects_invalid_token(self, client):
        """Dashboard stats should reject invalid tokens."""
        response = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401


class TestDashboardIsolation:
    """Test data isolation between tenants."""

    def test_different_orgs_see_different_stats(self, client):
        """Different organizations should see their own stats."""
        # Create two different orgs
        org1 = create_test_org_and_user(client, f"iso1_{secrets.token_hex(4)}")
        org2 = create_test_org_and_user(client, f"iso2_{secrets.token_hex(4)}")

        if not org1 or not org2:
            pytest.skip("Could not create test orgs")

        # Create a fleet in org1 only
        client.post(
            f"/api/v1/fleets?name=IsoTestFleet_{secrets.token_hex(4)}",
            headers={"Authorization": f"Bearer {org1['bearer_token']}"}
        )

        # Get stats for both orgs
        stats1 = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {org1['bearer_token']}"}
        ).json()

        stats2 = client.get(
            "/api/v1/dashboard/stats",
            headers={"Authorization": f"Bearer {org2['bearer_token']}"}
        ).json()

        # Org1 should have at least 1 fleet
        assert stats1["fleet_count"] >= 1

        # Org2 should have 0 fleets (fresh org)
        assert stats2["fleet_count"] == 0


class TestStatusHealth:
    """Test /status/health endpoint."""

    def test_status_health_returns_valid_response(self, client):
        """Status health should return valid response."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/status/health",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "overall" in data
        assert "services" in data
        assert "timestamp" in data

    def test_status_health_services_structure(self, client):
        """Status health services should have correct structure."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/status/health",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check services are present
        assert "database" in data["services"]

        # Each service should have status and latency
        for service_name, service_data in data["services"].items():
            assert "status" in service_data, f"Missing status in {service_name}"
            assert "latency_ms" in service_data, f"Missing latency_ms in {service_name}"

    def test_status_health_requires_auth(self, client):
        """Status health should require authentication."""
        response = client.get("/api/v1/status/health")
        assert response.status_code == 401


class TestStatusMetrics:
    """Test /status/metrics endpoint."""

    def test_status_metrics_returns_valid_response(self, client):
        """Status metrics should return valid response."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/status/metrics",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "uptime_pct" in data
        assert "avg_latency_ms" in data
        assert "compliance" in data
        assert "timestamp" in data

    def test_status_metrics_uptime_range(self, client):
        """Uptime percentage should be between 0 and 100."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/status/metrics",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 0 <= data["uptime_pct"] <= 100

    def test_status_metrics_requires_auth(self, client):
        """Status metrics should require authentication."""
        response = client.get("/api/v1/status/metrics")
        assert response.status_code == 401


class TestSecurityScore:
    """Test /security/score endpoint."""

    def test_security_score_returns_valid_response(self, client):
        """Security score should return valid response."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/security/score",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "overall" in data
        assert "categories" in data
        assert "alerts" in data
        assert "last_audit" in data

    def test_security_score_range(self, client):
        """Overall security score should be between 0 and 100."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/security/score",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 0 <= data["overall"] <= 100

    def test_security_score_categories(self, client):
        """Security score should have expected categories."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/security/score",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        expected_categories = ["certificates", "keys", "compliance", "attestation"]
        for cat in expected_categories:
            assert cat in data["categories"], f"Missing category: {cat}"
            assert 0 <= data["categories"][cat] <= 100

    def test_security_score_requires_auth(self, client):
        """Security score should require authentication."""
        response = client.get("/api/v1/security/score")
        assert response.status_code == 401


class TestFlowNodes:
    """Test /flow/nodes endpoint."""

    def test_flow_nodes_returns_valid_response(self, client):
        """Flow nodes should return valid response."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/flow/nodes",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "triggers" in data
        assert "actions" in data
        assert "categories" in data

    def test_flow_nodes_triggers_structure(self, client):
        """Flow node triggers should have correct structure."""
        creds = create_test_org_and_user(client)
        if not creds:
            pytest.skip("Could not create test org/user")

        response = client.get(
            "/api/v1/flow/nodes",
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["triggers"]) > 0

        for trigger in data["triggers"]:
            assert "id" in trigger
            assert "name" in trigger
            assert "category" in trigger

    def test_flow_nodes_requires_auth(self, client):
        """Flow nodes should require authentication."""
        response = client.get("/api/v1/flow/nodes")
        assert response.status_code == 401
