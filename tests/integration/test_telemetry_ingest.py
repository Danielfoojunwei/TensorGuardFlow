"""
Telemetry Ingestion Tests

Tests for the telemetry ingest endpoint including:
- Basic ingestion flow
- Idempotency (duplicate batch handling)
- Payload validation
- Fleet authentication

Run with: pytest tests/integration/test_telemetry_ingest.py -v
"""

import pytest
import time
import secrets


def get_test_client():
    """Get a test client using the app's default database."""
    from fastapi.testclient import TestClient
    from tensorguard.platform.main import app
    return TestClient(app, raise_server_exceptions=False)


def create_test_fleet(client) -> dict:
    """Create a test organization, user, and fleet. Returns credentials."""
    suffix = secrets.token_hex(4)
    email = f"ingest_test_{suffix}@test.com"
    password = "SecurePassword123!"
    org_name = f"IngestTestOrg_{suffix}"
    fleet_name = f"IngestTestFleet_{suffix}"

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
    login_resp = client.post(
        "/api/v1/auth/token",
        json={"username": email, "password": password}
    )
    if login_resp.status_code != 200:
        return None

    token = login_resp.json()["access_token"]

    # Create fleet
    fleet_resp = client.post(
        f"/api/v1/fleets?name={fleet_name}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if fleet_resp.status_code != 200:
        return None

    fleet_data = fleet_resp.json()
    return {
        "fleet_id": fleet_data["id"],
        "api_key": fleet_data["api_key"],
        "bearer_token": token
    }


class TestTelemetryIngestBasic:
    """Test basic telemetry ingestion functionality."""

    @pytest.fixture
    def fleet_credentials(self):
        """Create a fleet and return its credentials."""
        client = get_test_client()
        creds = create_test_fleet(client)
        if not creds:
            pytest.skip("Could not create test fleet")
        return creds

    def test_ingest_accepts_valid_batch(self, fleet_credentials):
        """Valid telemetry batch should be accepted."""
        client = get_test_client()
        batch_id = f"valid_batch_{secrets.token_hex(4)}"

        payload = {
            "batch_id": batch_id,
            "device_info": {"device_id": "test-device-001"},
            "messages": [
                {
                    "topic": "telemetry.stage",
                    "timestamp_ns": int(time.time() * 1e9),
                    "payload": {
                        "device_id": "test-device-001",
                        "stage": "capture",
                        "status": "ok",
                        "latency_ms": 50.0
                    },
                    "priority": 0
                }
            ]
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )

        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0
        assert data["is_duplicate"] is False

    def test_ingest_accepts_empty_messages(self, fleet_credentials):
        """Empty message list should be accepted (for heartbeat)."""
        client = get_test_client()
        batch_id = f"empty_batch_{secrets.token_hex(4)}"

        payload = {
            "batch_id": batch_id,
            "device_info": {"device_id": "heartbeat-device"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 0
        assert data["rejected"] == 0

    def test_ingest_multiple_topics(self, fleet_credentials):
        """Batch with multiple topic types should be accepted."""
        client = get_test_client()
        batch_id = f"multi_topic_{secrets.token_hex(4)}"
        ts = int(time.time() * 1e9)

        payload = {
            "batch_id": batch_id,
            "device_info": {"device_id": "multi-device"},
            "messages": [
                {
                    "topic": "telemetry.stage",
                    "timestamp_ns": ts,
                    "payload": {
                        "device_id": "multi-device",
                        "stage": "embed",
                        "status": "ok",
                        "latency_ms": 30.0
                    },
                    "priority": 0
                },
                {
                    "topic": "telemetry.system",
                    "timestamp_ns": ts,
                    "payload": {
                        "device_id": "multi-device",
                        "cpu_pct": 45.0,
                        "mem_pct": 60.0
                    },
                    "priority": 0
                }
            ]
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 2
        assert data["rejected"] == 0


class TestTelemetryIdempotency:
    """Test idempotency handling for duplicate batch submissions."""

    @pytest.fixture
    def fleet_credentials(self):
        """Create a fleet and return its credentials."""
        client = get_test_client()
        creds = create_test_fleet(client)
        if not creds:
            pytest.skip("Could not create test fleet")
        return creds

    def test_duplicate_batch_is_ignored(self, fleet_credentials):
        """Submitting the same batch_id twice should be idempotent."""
        client = get_test_client()
        batch_id = f"dupe_test_{secrets.token_hex(4)}"

        payload = {
            "batch_id": batch_id,
            "device_info": {"device_id": "dupe-device"},
            "messages": [
                {
                    "topic": "telemetry.stage",
                    "timestamp_ns": int(time.time() * 1e9),
                    "payload": {
                        "device_id": "dupe-device",
                        "stage": "gate",
                        "status": "ok",
                        "latency_ms": 20.0
                    },
                    "priority": 0
                }
            ]
        }

        # First submission
        response1 = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["accepted"] == 1
        assert data1["is_duplicate"] is False

        # Second submission with same batch_id
        response2 = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["accepted"] == 0
        assert data2["is_duplicate"] is True

    def test_different_batch_ids_not_duplicate(self, fleet_credentials):
        """Different batch_ids should not be treated as duplicates."""
        client = get_test_client()
        suffix = secrets.token_hex(4)

        base_payload = {
            "device_info": {"device_id": "different-device"},
            "messages": []
        }

        # First batch
        payload1 = {**base_payload, "batch_id": f"batch_a_{suffix}"}
        response1 = client.post(
            "/api/v1/telemetry/ingest",
            json=payload1,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )
        assert response1.status_code == 200
        assert response1.json()["is_duplicate"] is False

        # Second batch with different ID
        payload2 = {**base_payload, "batch_id": f"batch_b_{suffix}"}
        response2 = client.post(
            "/api/v1/telemetry/ingest",
            json=payload2,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )
        assert response2.status_code == 200
        assert response2.json()["is_duplicate"] is False


class TestTelemetryValidation:
    """Test payload validation for telemetry ingestion."""

    @pytest.fixture
    def fleet_credentials(self):
        """Create a fleet and return its credentials."""
        client = get_test_client()
        creds = create_test_fleet(client)
        if not creds:
            pytest.skip("Could not create test fleet")
        return creds

    def test_missing_batch_id_rejected(self, fleet_credentials):
        """Request without batch_id should be rejected."""
        client = get_test_client()

        payload = {
            "device_info": {"device_id": "no-batch"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )

        # Should fail validation (422)
        assert response.status_code == 422

    def test_invalid_topic_counted_as_rejected(self, fleet_credentials):
        """Unknown topic should be rejected in response."""
        client = get_test_client()
        batch_id = f"invalid_topic_{secrets.token_hex(4)}"

        payload = {
            "batch_id": batch_id,
            "device_info": {"device_id": "invalid-topic-device"},
            "messages": [
                {
                    "topic": "telemetry.unknown_topic",
                    "timestamp_ns": int(time.time() * 1e9),
                    "payload": {"device_id": "invalid-topic-device"},
                    "priority": 0
                }
            ]
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Fleet {fleet_credentials['api_key']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rejected"] == 1
        assert len(data["rejections"]) == 1
        assert "unknown topic" in data["rejections"][0]["reason"]


class TestTelemetryAuthentication:
    """Test Fleet authentication for telemetry ingestion."""

    def test_ingest_rejects_no_auth(self):
        """Request without auth should be rejected."""
        client = get_test_client()

        payload = {
            "batch_id": "no_auth_batch",
            "device_info": {"device_id": "no-auth"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload
        )

        assert response.status_code == 401

    def test_ingest_rejects_invalid_fleet_key(self):
        """Invalid Fleet key should be rejected."""
        client = get_test_client()

        payload = {
            "batch_id": "invalid_key_batch",
            "device_info": {"device_id": "invalid-key"},
            "messages": []
        }

        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": "Fleet invalid_api_key_12345"}
        )

        assert response.status_code == 401

    def test_ingest_rejects_bearer_token(self):
        """Bearer token (user auth) should not work for Fleet endpoint."""
        client = get_test_client()
        creds = create_test_fleet(client)

        if not creds:
            pytest.skip("Could not create test fleet")

        payload = {
            "batch_id": "bearer_test_batch",
            "device_info": {"device_id": "bearer-test"},
            "messages": []
        }

        # Try with Bearer token instead of Fleet
        response = client.post(
            "/api/v1/telemetry/ingest",
            json=payload,
            headers={"Authorization": f"Bearer {creds['bearer_token']}"}
        )

        # Should fail - this endpoint requires Fleet auth, not Bearer
        assert response.status_code == 401
