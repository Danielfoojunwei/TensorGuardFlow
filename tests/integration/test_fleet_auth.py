"""
Tests for Fleet Bearer authentication.

Verifies:
- Valid Fleet API key returns 200
- Missing Authorization header returns 401
- Invalid key format returns 401
- Revoked/inactive fleet returns 403
- Wrong API key returns 401
"""

import hashlib
import uuid
import time
import pytest


class TestFleetBearerAuth:
    """Tests for Fleet Bearer authentication."""

    def test_missing_auth_header_returns_401(self, client):
        """Missing Authorization header should return 401."""
        response = client.post(
            "/api/v1/telemetry/ingest",
            json={
                "batch_id": "test-batch-001",
                "messages": []
            }
        )
        assert response.status_code == 401
        assert "Fleet" in response.headers.get("WWW-Authenticate", "")

    def test_invalid_auth_scheme_returns_401(self, client):
        """Using Bearer instead of Fleet scheme should return 401."""
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": "Bearer some-token"},
            json={
                "batch_id": "test-batch-001",
                "messages": []
            }
        )
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, client):
        """Malformed Authorization header should return 401."""
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": "Fleet"},  # Missing key
            json={
                "batch_id": "test-batch-001",
                "messages": []
            }
        )
        assert response.status_code == 401

    def test_invalid_fleet_key_returns_401(self, client):
        """Invalid Fleet API key should return 401."""
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": "Fleet invalid-key-that-does-not-exist"},
            json={
                "batch_id": "test-batch-001",
                "messages": []
            }
        )
        assert response.status_code == 401

    def test_valid_fleet_key_with_batch(self, client, session):
        """Valid Fleet API key should allow telemetry ingestion."""
        from tensorguard.platform.models.core import Fleet, Tenant

        # Create tenant and fleet with known API key
        tenant_id = str(uuid.uuid4())
        fleet_id = str(uuid.uuid4())
        raw_api_key = f"tgf_{uuid.uuid4().hex}"
        api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant for Fleet Auth",
            slug=f"test-fleet-auth-{uuid.uuid4().hex[:8]}"
        )
        session.add(tenant)

        fleet = Fleet(
            id=fleet_id,
            tenant_id=tenant_id,
            name="Test Fleet for Auth",
            api_key_hash=api_key_hash,
            is_active=True,
        )
        session.add(fleet)
        session.commit()

        # Make request with valid Fleet Bearer auth
        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": f"Fleet {raw_api_key}"},
            json={
                "batch_id": "test-batch-valid",
                "messages": []
            }
        )

        # Should succeed with 200 and return ingestion result
        assert response.status_code == 200
        data = response.json()
        assert "accepted" in data
        assert "rejected" in data
        assert data["accepted"] == 0  # Empty batch
        assert data["rejected"] == 0

    def test_inactive_fleet_returns_403(self, client, session):
        """Inactive fleet should return 403."""
        from tensorguard.platform.models.core import Fleet, Tenant

        tenant_id = str(uuid.uuid4())
        fleet_id = str(uuid.uuid4())
        raw_api_key = f"tgf_{uuid.uuid4().hex}"
        api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant for Inactive Fleet",
            slug=f"test-inactive-{uuid.uuid4().hex[:8]}"
        )
        session.add(tenant)

        # Create inactive fleet
        fleet = Fleet(
            id=fleet_id,
            tenant_id=tenant_id,
            name="Inactive Fleet",
            api_key_hash=api_key_hash,
            is_active=False,  # Inactive!
        )
        session.add(fleet)
        session.commit()

        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": f"Fleet {raw_api_key}"},
            json={
                "batch_id": "test-batch-inactive",
                "messages": []
            }
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_telemetry_ingestion_with_messages(self, client, session):
        """Test actual telemetry ingestion with valid messages."""
        from tensorguard.platform.models.core import Fleet, Tenant

        tenant_id = str(uuid.uuid4())
        fleet_id = str(uuid.uuid4())
        raw_api_key = f"tgf_{uuid.uuid4().hex}"
        api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant for Ingestion",
            slug=f"test-ingest-{uuid.uuid4().hex[:8]}"
        )
        session.add(tenant)

        fleet = Fleet(
            id=fleet_id,
            tenant_id=tenant_id,
            name="Ingestion Test Fleet",
            api_key_hash=api_key_hash,
            is_active=True,
        )
        session.add(fleet)
        session.commit()

        ts_ns = int(time.time() * 1_000_000_000)

        response = client.post(
            "/api/v1/telemetry/ingest",
            headers={"Authorization": f"Fleet {raw_api_key}"},
            json={
                "batch_id": f"test-batch-{uuid.uuid4().hex[:8]}",
                "device_info": {
                    "device_id": f"device-{uuid.uuid4().hex[:8]}",
                    "agent_version": "1.0.0",
                },
                "messages": [
                    {
                        "topic": "telemetry.stage",
                        "timestamp_ns": ts_ns,
                        "payload": {
                            "stage": "capture",
                            "status": "ok",
                            "latency_ms": 12.5,
                        }
                    },
                    {
                        "topic": "telemetry.system",
                        "timestamp_ns": ts_ns,
                        "payload": {
                            "cpu_pct": 45.2,
                            "mem_pct": 62.1,
                        }
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 2
        assert data["rejected"] == 0
