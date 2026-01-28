"""
Contract tests for OutboundOpsEvent schema.

Verifies that OutboundOpsEvent schema correctly validates events
and produces expected JSON output.
"""

import json
import pytest
from datetime import datetime

from tensorguard.integrations.connectors.robotics.schemas import (
    OutboundOpsEvent,
    EventPayload,
    EvidenceRefs,
    ActionContext,
    Severity,
    EventCategory,
    OutboundEventType,
)


class TestOutboundOpsEventSchema:
    """Test OutboundOpsEvent Pydantic model."""

    def test_minimal_event_creation(self):
        """Test creating event with minimal required fields."""
        event = OutboundOpsEvent(
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Adapter promoted to production",
        )

        assert event.tenant_id == "test-tenant"
        assert event.route_key == "test-route"
        assert event.severity == Severity.INFO
        assert event.category == EventCategory.RELEASE
        assert event.type == OutboundEventType.PROMOTED
        assert event.summary == "Adapter promoted to production"
        assert event.event_id.startswith("evt_")
        assert event.schema_version == "1.0"

    def test_event_with_full_payload(self):
        """Test creating event with complete payload."""
        event = OutboundOpsEvent(
            tenant_id="test-tenant",
            route_key="nav-policy-prod",
            severity=Severity.CRITICAL,
            category=EventCategory.RELEASE,
            type=OutboundEventType.ROLLBACK,
            summary="Automatic rollback triggered",
            payload=EventPayload(
                adapter_id="adpt_abc123",
                run_id="run-20260128-001",
                base_model="meta-llama/Llama-3.1-8B",
                metrics_snapshot={
                    "safety_score": 0.72,
                    "latency_p99_ms": 120,
                },
                evidence_refs=EvidenceRefs(
                    tgsp_uri="tgsp://tenant/route/run.tgsp",
                    evidence_uri="s3://evidence/run/evidence.json",
                    policy_hash="sha256:abc123",
                ),
                action_context=ActionContext(
                    triggered_by="ops_signal",
                    reason="Safety regression detected",
                    previous_adapter_id="adpt_abc123",
                    rollback_target_adapter_id="adpt_abc122",
                    signal_id="sig_xyz789",
                ),
            ),
        )

        assert event.payload.adapter_id == "adpt_abc123"
        assert event.payload.metrics_snapshot["safety_score"] == 0.72
        assert event.payload.evidence_refs.tgsp_uri == "tgsp://tenant/route/run.tgsp"
        assert event.payload.action_context.triggered_by == "ops_signal"

    def test_event_to_json_serialization(self):
        """Test JSON serialization."""
        event = OutboundOpsEvent(
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.WARN,
            category=EventCategory.TRUST,
            type=OutboundEventType.SIGNATURE_FAILED,
            summary="Signature verification failed",
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["tenant_id"] == "test-tenant"
        assert parsed["severity"] == "WARN"
        assert parsed["category"] == "TRUST"
        assert parsed["type"] == "signature_failed"

    def test_event_idempotency_key(self):
        """Test idempotency key generation."""
        event = OutboundOpsEvent(
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        key = event.compute_idempotency_key()
        assert key == event.event_id

    def test_event_checksum(self):
        """Test checksum computation."""
        event = OutboundOpsEvent(
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        checksum = event.compute_checksum()
        assert len(checksum) == 64  # SHA256 hex

    def test_summary_max_length(self):
        """Test summary field max length validation."""
        with pytest.raises(Exception):  # Pydantic validation error
            OutboundOpsEvent(
                tenant_id="test-tenant",
                route_key="test-route",
                severity=Severity.INFO,
                category=EventCategory.RELEASE,
                type=OutboundEventType.PROMOTED,
                summary="x" * 300,  # Exceeds 256 char limit
            )

    def test_all_severity_levels(self):
        """Test all severity levels are valid."""
        for severity in [Severity.INFO, Severity.WARN, Severity.CRITICAL]:
            event = OutboundOpsEvent(
                tenant_id="test",
                route_key="test",
                severity=severity,
                category=EventCategory.RELEASE,
                type=OutboundEventType.PROMOTED,
                summary="Test",
            )
            assert event.severity == severity

    def test_all_event_types(self):
        """Test all event types are valid."""
        for event_type in OutboundEventType:
            event = OutboundOpsEvent(
                tenant_id="test",
                route_key="test",
                severity=Severity.INFO,
                category=EventCategory.RELEASE,
                type=event_type,
                summary="Test",
            )
            assert event.type == event_type

    def test_all_categories(self):
        """Test all event categories are valid."""
        for category in EventCategory:
            event = OutboundOpsEvent(
                tenant_id="test",
                route_key="test",
                severity=Severity.INFO,
                category=category,
                type=OutboundEventType.PROMOTED,
                summary="Test",
            )
            assert event.category == category

    def test_timestamp_format(self):
        """Test timestamp is ISO8601 format."""
        event = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        # Should parse as ISO8601
        ts = event.ts
        assert ts.endswith("Z")
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
