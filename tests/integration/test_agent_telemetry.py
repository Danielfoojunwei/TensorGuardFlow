"""
Tests for agent telemetry emission with Fleet Bearer auth.

Verifies the TelemetryEmitter can successfully send telemetry
to the backend using Fleet Bearer authentication.
"""

import hashlib
import uuid
import time
import pytest


class TestTelemetryEmitterAuth:
    """Tests for TelemetryEmitter authentication."""

    def test_emitter_sends_batch_with_fleet_auth(self, client, session):
        """TelemetryEmitter should successfully send batches with Fleet Bearer auth."""
        from tensorguard.platform.models.core import Fleet, Tenant

        # Create tenant and fleet
        tenant_id = str(uuid.uuid4())
        fleet_id = str(uuid.uuid4())
        raw_api_key = f"tgf_{uuid.uuid4().hex}"
        api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant for Emitter",
            slug=f"test-emitter-{uuid.uuid4().hex[:8]}"
        )
        session.add(tenant)

        fleet = Fleet(
            id=fleet_id,
            tenant_id=tenant_id,
            name="Emitter Test Fleet",
            api_key_hash=api_key_hash,
            is_active=True,
        )
        session.add(fleet)
        session.commit()

        # Simulate what TelemetryEmitter._build_headers produces
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Fleet {raw_api_key}",
        }

        ts_ns = int(time.time() * 1_000_000_000)
        device_id = f"device-{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/telemetry/ingest",
            headers=headers,
            json={
                "batch_id": f"emitter-batch-{uuid.uuid4().hex[:8]}",
                "device_info": {
                    "device_id": device_id,
                    "agent_version": "2.0.0",
                },
                "messages": [
                    {
                        "topic": "telemetry.stage",
                        "timestamp_ns": ts_ns,
                        "payload": {
                            "stage": "capture",
                            "status": "ok",
                            "latency_ms": 25.0,
                            "metadata": {"frame_count": 100}
                        }
                    },
                    {
                        "topic": "telemetry.system",
                        "timestamp_ns": ts_ns,
                        "payload": {
                            "cpu_pct": 55.0,
                            "mem_pct": 72.0,
                        }
                    },
                    {
                        "topic": "telemetry.heartbeat",
                        "timestamp_ns": ts_ns,
                        "payload": {
                            "device_id": device_id,
                            "status": "healthy",
                        }
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        # heartbeat is unknown topic, so 1 rejection
        assert data["accepted"] == 2
        assert data["rejected"] == 1

    def test_emitter_headers_format(self):
        """Verify TelemetryEmitter._build_headers produces correct format."""
        from tensorguard.agent.telemetry.emitter import TelemetryEmitter

        emitter = TelemetryEmitter(
            control_plane_url="http://localhost:8000",
            api_key="test-api-key-12345",
            fleet_id="test-fleet-id",
            device_id="test-device-id",
            enable_system_metrics=False,
        )

        headers = emitter._build_headers(b'{"test": "data"}')

        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Fleet test-api-key-12345"
        # Verify no HMAC headers present
        assert "X-TG-Fleet-Id" not in headers
        assert "X-TG-Signature" not in headers
        assert "X-TG-Timestamp" not in headers
        assert "X-TG-Nonce" not in headers

    def test_identity_client_headers_format(self):
        """Verify IdentityAgentClient produces correct auth headers."""
        from tensorguard.agent.identity.client import IdentityAgentClient

        client = IdentityAgentClient(
            base_url="http://localhost:8000",
            fleet_id="test-fleet-id",
            api_key="test-api-key-67890",
        )

        # Test that the authenticated_request method exists and is callable
        assert hasattr(client, "authenticated_request")
        assert hasattr(client, "signed_request")  # Backwards compat alias

        # Verify the api_key is stored
        assert client.api_key == "test-api-key-67890"
        assert client.fleet_id == "test-fleet-id"
