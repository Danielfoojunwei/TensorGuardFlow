"""
Contract tests for outbound event idempotency.

Verifies that event_id is used for idempotent delivery.
"""

import pytest

from tensorguard.integrations.connectors.robotics.schemas import (
    OutboundOpsEvent,
    EventPayload,
    Severity,
    EventCategory,
    OutboundEventType,
)


class TestOutboundIdempotency:
    """Test outbound event idempotency via event_id."""

    def test_event_id_is_unique(self):
        """Test that each event gets a unique ID."""
        event1 = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        event2 = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        assert event1.event_id != event2.event_id

    def test_event_id_format(self):
        """Test event ID format."""
        event = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        assert event.event_id.startswith("evt_")
        assert len(event.event_id) == 28  # evt_ + 24 hex chars

    def test_idempotency_key_equals_event_id(self):
        """Test that idempotency key is the event_id."""
        event = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        assert event.compute_idempotency_key() == event.event_id

    def test_explicit_event_id_is_preserved(self):
        """Test that explicitly set event_id is preserved."""
        custom_id = "evt_custom123456789012345678"

        event = OutboundOpsEvent(
            event_id=custom_id,
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Test",
        )

        assert event.event_id == custom_id

    def test_same_content_different_ids(self):
        """Test that identical content produces different event_ids."""
        payload = EventPayload(
            adapter_id="adpt_abc123",
            run_id="run-001",
        )

        events = []
        for _ in range(100):
            event = OutboundOpsEvent(
                tenant_id="test",
                route_key="test",
                severity=Severity.INFO,
                category=EventCategory.RELEASE,
                type=OutboundEventType.PROMOTED,
                summary="Same content",
                payload=payload,
            )
            events.append(event.event_id)

        # All event IDs should be unique
        assert len(set(events)) == 100

    def test_checksum_same_for_same_content(self):
        """Test that checksum is deterministic for same content."""
        def create_event():
            return OutboundOpsEvent(
                event_id="evt_fixed123456789012345678",  # Fix event_id
                ts="2026-01-28T12:00:00Z",  # Fix timestamp
                tenant_id="test",
                route_key="test",
                severity=Severity.INFO,
                category=EventCategory.RELEASE,
                type=OutboundEventType.PROMOTED,
                summary="Test",
            )

        event1 = create_event()
        event2 = create_event()

        # Checksums should match (event_id excluded from checksum)
        assert event1.compute_checksum() == event2.compute_checksum()

    def test_checksum_differs_for_different_content(self):
        """Test that checksum differs for different content."""
        event1 = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Summary A",
        )

        event2 = OutboundOpsEvent(
            tenant_id="test",
            route_key="test",
            severity=Severity.INFO,
            category=EventCategory.RELEASE,
            type=OutboundEventType.PROMOTED,
            summary="Summary B",
        )

        assert event1.compute_checksum() != event2.compute_checksum()
