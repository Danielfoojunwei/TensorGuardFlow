"""
Integration test: Critical incident triggers rollback when allowed.

Verifies end-to-end flow from inbound signal to rollback action.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from tensorguard.integrations.connectors.robotics.schemas import (
    InboundOpsSignal,
    SignalPayload,
    NormalizedSignalData,
    AuthInfo,
    SignalSource,
    InboundSignalType,
    Severity,
    ActionType,
)
from tensorguard.platform.services.ops_signal_router import (
    OpsSignalRouter,
    OpsSignalPolicy,
)


class TestCriticalIncidentTriggersRollback:
    """Test that critical incidents trigger rollback when allowed."""

    @pytest.fixture
    def rollback_callback(self):
        """Create mock rollback callback."""
        callback = MagicMock(return_value=True)
        return callback

    @pytest.fixture
    def router_with_rollback_allowed(self, rollback_callback):
        """Create router with rollback allowed."""
        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_rollback=True,
                allow_auto_freeze=True,
                require_verified_signature_for_automation=False,
            )

        return OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=get_policy,
        )

    @pytest.fixture
    def router_with_rollback_blocked(self, rollback_callback):
        """Create router with rollback blocked."""
        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_rollback=False,  # Blocked
                allow_auto_freeze=True,
                require_verified_signature_for_automation=False,
            )

        return OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=get_policy,
        )

    @pytest.fixture
    def critical_regression_signal(self):
        """Create a critical regression signal."""
        return InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="nav-policy-prod",
            severity=Severity.CRITICAL,
            type=InboundSignalType.REGRESSION_DETECTED,
            payload=SignalPayload(
                raw={
                    "event_type": "metric.threshold.exceeded",
                    "robot_id": "robot-001",
                    "metric": "safety_score",
                    "value": 0.72,
                    "threshold": 0.85,
                },
                normalized=NormalizedSignalData(
                    metrics={"safety_score": 0.72},
                    affected_agents=["robot-001"],
                ),
            ),
            auth=AuthInfo(
                signature_present=True,
                verified=True,
            ),
            dedupe_key="inorbit:regression:robot-001:12345",
        )

    @pytest.mark.asyncio
    async def test_critical_regression_triggers_rollback_when_allowed(
        self,
        router_with_rollback_allowed,
        rollback_callback,
        critical_regression_signal,
    ):
        """Test that critical regression triggers rollback when policy allows."""
        result = await router_with_rollback_allowed.route_signal(
            critical_regression_signal
        )

        assert result.success is True
        assert result.action == ActionType.ROLLBACK_ROUTE
        assert rollback_callback.called

    @pytest.mark.asyncio
    async def test_critical_regression_blocked_when_not_allowed(
        self,
        router_with_rollback_blocked,
        rollback_callback,
        critical_regression_signal,
    ):
        """Test that rollback is blocked when policy disallows."""
        result = await router_with_rollback_blocked.route_signal(
            critical_regression_signal
        )

        assert result.success is False
        assert "blocked" in result.message.lower()
        assert not rollback_callback.called

    @pytest.mark.asyncio
    async def test_safety_stop_triggers_quarantine(self):
        """Test that safety stop triggers quarantine action."""
        quarantine_callback = MagicMock(return_value=True)

        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_quarantine=True,
                require_verified_signature_for_automation=False,
            )

        router = OpsSignalRouter(
            on_quarantine=quarantine_callback,
            get_route_policy=get_policy,
        )

        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="nav-policy-prod",
            severity=Severity.CRITICAL,
            type=InboundSignalType.SAFETY_STOP,
            payload=SignalPayload(
                raw={"event": "emergency_stop"},
            ),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="inorbit:safety:12345",
        )

        result = await router.route_signal(signal)

        assert result.success is True
        assert result.action == ActionType.QUARANTINE_ADAPTER
        assert quarantine_callback.called

    @pytest.mark.asyncio
    async def test_manual_rollback_request_triggers_rollback(self):
        """Test that manual rollback request triggers rollback."""
        rollback_callback = MagicMock(return_value=True)

        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_rollback=True,
                require_verified_signature_for_automation=False,
            )

        router = OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=get_policy,
        )

        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.FORMANT,
            tenant_id="test-tenant",
            route_key="nav-policy-prod",
            severity=Severity.WARN,  # Even with WARN severity
            type=InboundSignalType.MANUAL_ROLLBACK_REQUEST,
            payload=SignalPayload(
                raw={"reason": "Operator requested rollback"},
                normalized=NormalizedSignalData(
                    operator_notes="Production issue observed",
                ),
            ),
            auth=AuthInfo(signature_present=True, verified=True),
            dedupe_key="formant:rollback:12345",
        )

        result = await router.route_signal(signal)

        assert result.success is True
        assert result.action == ActionType.ROLLBACK_ROUTE
        assert rollback_callback.called

    @pytest.mark.asyncio
    async def test_evidence_event_recorded_on_rollback(
        self,
        router_with_rollback_allowed,
        critical_regression_signal,
    ):
        """Test that evidence event is recorded on rollback."""
        await router_with_rollback_allowed.route_signal(critical_regression_signal)

        events = router_with_rollback_allowed.get_evidence_events(
            route_key="nav-policy-prod"
        )

        # Should have at least signal received and rollback triggered events
        assert len(events) >= 2

        event_types = [e.event_type.value for e in events]
        assert "ops_signal_received" in event_types
        assert "auto_rollback_triggered" in event_types
