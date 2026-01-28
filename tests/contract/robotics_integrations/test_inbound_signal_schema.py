"""
Contract tests for InboundOpsSignal schema.

Verifies that InboundOpsSignal schema correctly validates signals
and enforces constraints.
"""

import json
import pytest
from datetime import datetime

from tensorguard.integrations.connectors.robotics.schemas import (
    InboundOpsSignal,
    SignalPayload,
    NormalizedSignalData,
    ThresholdViolation,
    AuthInfo,
    SignalSource,
    InboundSignalType,
    Severity,
    ActionType,
    get_default_action_for_signal,
)


class TestInboundOpsSignalSchema:
    """Test InboundOpsSignal Pydantic model."""

    def test_minimal_signal_creation(self):
        """Test creating signal with minimal required fields."""
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.WARN,
            type=InboundSignalType.INCIDENT,
            payload=SignalPayload(
                raw={"event": "test"},
            ),
            auth=AuthInfo(signature_present=False, verified=True),
            dedupe_key="test-dedupe-key",
        )

        assert signal.source == SignalSource.INORBIT
        assert signal.tenant_id == "test-tenant"
        assert signal.route_key == "test-route"
        assert signal.severity == Severity.WARN
        assert signal.type == InboundSignalType.INCIDENT
        assert signal.signal_id.startswith("sig_")

    def test_signal_with_tenant_hint(self):
        """Test signal with tenant_hint instead of tenant_id."""
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.FORMANT,
            tenant_hint="robot-alpha-001",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.SAFETY_STOP,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="test-key",
        )

        assert signal.tenant_hint == "robot-alpha-001"
        assert signal.tenant_id is None

    def test_signal_requires_tenant_identification(self):
        """Test that at least one tenant identifier is required."""
        with pytest.raises(ValueError):
            InboundOpsSignal(
                ts="2026-01-28T12:00:00Z",
                source=SignalSource.INORBIT,
                # Neither tenant_id nor tenant_hint
                route_key="test-route",
                severity=Severity.WARN,
                type=InboundSignalType.INCIDENT,
                payload=SignalPayload(raw={}),
                auth=AuthInfo(signature_present=False, verified=True),
                dedupe_key="test-key",
            )

    def test_signal_rejects_info_severity(self):
        """Test that INFO severity is rejected for inbound signals."""
        with pytest.raises(ValueError):
            InboundOpsSignal(
                ts="2026-01-28T12:00:00Z",
                source=SignalSource.INORBIT,
                tenant_id="test",
                route_key="test-route",
                severity=Severity.INFO,  # Should be rejected
                type=InboundSignalType.INCIDENT,
                payload=SignalPayload(raw={}),
                auth=AuthInfo(signature_present=False, verified=True),
                dedupe_key="test-key",
            )

    def test_signal_with_threshold_violation(self):
        """Test signal with threshold violation details."""
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.REGRESSION_DETECTED,
            payload=SignalPayload(
                raw={"metric": "safety_score", "value": 0.72},
                normalized=NormalizedSignalData(
                    metrics={"safety_score": 0.72},
                    threshold_violation=ThresholdViolation(
                        metric_name="safety_score",
                        current_value=0.72,
                        threshold_value=0.85,
                        direction="below",
                    ),
                ),
            ),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="test-key",
        )

        assert signal.payload.normalized.threshold_violation.metric_name == "safety_score"
        assert signal.payload.normalized.threshold_violation.direction == "below"

    def test_threshold_violation_direction_validation(self):
        """Test threshold violation direction validation."""
        with pytest.raises(ValueError):
            ThresholdViolation(
                metric_name="test",
                current_value=1.0,
                threshold_value=0.5,
                direction="invalid",  # Should be "above" or "below"
            )

    def test_signal_is_critical(self):
        """Test is_critical() helper method."""
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.SAFETY_STOP,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="test-key",
        )

        assert signal.is_critical() is True

    def test_signal_requires_immediate_action(self):
        """Test requires_immediate_action() helper method."""
        # Safety stop always requires immediate action
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test",
            route_key="test-route",
            severity=Severity.WARN,  # Even with WARN
            type=InboundSignalType.SAFETY_STOP,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="test-key",
        )

        assert signal.requires_immediate_action() is True

    def test_all_signal_sources(self):
        """Test all signal sources are valid."""
        for source in SignalSource:
            signal = InboundOpsSignal(
                ts="2026-01-28T12:00:00Z",
                source=source,
                tenant_id="test",
                route_key="test-route",
                severity=Severity.WARN,
                type=InboundSignalType.INCIDENT,
                payload=SignalPayload(raw={}),
                auth=AuthInfo(signature_present=False, verified=True),
                dedupe_key="test-key",
            )
            assert signal.source == source

    def test_all_signal_types(self):
        """Test all signal types are valid."""
        for signal_type in InboundSignalType:
            signal = InboundOpsSignal(
                ts="2026-01-28T12:00:00Z",
                source=SignalSource.GENERIC,
                tenant_id="test",
                route_key="test-route",
                severity=Severity.WARN,
                type=signal_type,
                payload=SignalPayload(raw={}),
                auth=AuthInfo(signature_present=False, verified=True),
                dedupe_key=f"test-{signal_type.value}",
            )
            assert signal.type == signal_type

    def test_auth_info_states(self):
        """Test different auth info states."""
        # Signature present and verified
        auth1 = AuthInfo(signature_present=True, verified=True, key_id="key-123")
        assert auth1.verified is True

        # Signature present but not verified
        auth2 = AuthInfo(
            signature_present=True,
            verified=False,
            verification_error="Invalid signature",
        )
        assert auth2.verified is False
        assert auth2.verification_error == "Invalid signature"

        # No signature present
        auth3 = AuthInfo(signature_present=False, verified=True)
        assert auth3.signature_present is False


class TestSignalToActionMapping:
    """Test signal type to action mapping."""

    def test_safety_stop_maps_to_quarantine(self):
        """Safety stop should map to quarantine."""
        action = get_default_action_for_signal(
            InboundSignalType.SAFETY_STOP,
            Severity.CRITICAL,
        )
        assert action == ActionType.QUARANTINE_ADAPTER

    def test_regression_maps_to_rollback(self):
        """Regression detected should map to rollback."""
        action = get_default_action_for_signal(
            InboundSignalType.REGRESSION_DETECTED,
            Severity.CRITICAL,
        )
        assert action == ActionType.ROLLBACK_ROUTE

    def test_manual_rollback_request_maps_to_rollback(self):
        """Manual rollback request should map to rollback."""
        action = get_default_action_for_signal(
            InboundSignalType.MANUAL_ROLLBACK_REQUEST,
            Severity.WARN,
        )
        assert action == ActionType.ROLLBACK_ROUTE

    def test_freeze_request_maps_to_freeze(self):
        """Freeze request should map to freeze."""
        action = get_default_action_for_signal(
            InboundSignalType.FREEZE_REQUEST,
            Severity.WARN,
        )
        assert action == ActionType.FREEZE_ROUTE

    def test_incident_maps_to_investigation(self):
        """Generic incident should map to investigation."""
        action = get_default_action_for_signal(
            InboundSignalType.INCIDENT,
            Severity.WARN,
        )
        assert action == ActionType.OPEN_INVESTIGATION

    def test_critical_severity_escalates_investigation_to_freeze(self):
        """Critical severity should escalate investigation to freeze."""
        action = get_default_action_for_signal(
            InboundSignalType.DRIFT_DETECTED,  # Normally investigation
            Severity.CRITICAL,  # But critical escalates
        )
        assert action == ActionType.FREEZE_ROUTE
