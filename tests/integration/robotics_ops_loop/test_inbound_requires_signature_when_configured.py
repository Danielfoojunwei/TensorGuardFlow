"""
Integration test: Signature verification requirement.

Verifies that automated actions are blocked when signature is required
but not verified.
"""

import pytest
from unittest.mock import MagicMock

from tensorguard.integrations.connectors.robotics.schemas import (
    InboundOpsSignal,
    SignalPayload,
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


class TestSignatureRequirementEnforcement:
    """Test that signature requirement is enforced."""

    @pytest.fixture
    def strict_signature_policy(self):
        """Policy requiring verified signature for automation."""
        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_rollback=True,
                allow_auto_freeze=True,
                require_verified_signature_for_automation=True,  # Required
            )
        return get_policy

    @pytest.fixture
    def lax_signature_policy(self):
        """Policy not requiring signature verification."""
        def get_policy(route_key):
            return OpsSignalPolicy(
                allow_auto_rollback=True,
                allow_auto_freeze=True,
                require_verified_signature_for_automation=False,  # Not required
            )
        return get_policy

    @pytest.fixture
    def verified_signal(self):
        """Signal with verified signature."""
        return InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.REGRESSION_DETECTED,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(
                signature_present=True,
                verified=True,
                key_id="inorbit-key-2026",
            ),
            dedupe_key="test-verified",
        )

    @pytest.fixture
    def unverified_signal(self):
        """Signal with unverified signature."""
        return InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.REGRESSION_DETECTED,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(
                signature_present=True,
                verified=False,  # Not verified
                verification_error="Signature mismatch",
            ),
            dedupe_key="test-unverified",
        )

    @pytest.fixture
    def no_signature_signal(self):
        """Signal without signature."""
        return InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.GENERIC,
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.CRITICAL,
            type=InboundSignalType.REGRESSION_DETECTED,
            payload=SignalPayload(raw={}),
            auth=AuthInfo(
                signature_present=False,  # No signature
                verified=False,
            ),
            dedupe_key="test-no-sig",
        )

    @pytest.mark.asyncio
    async def test_verified_signature_allows_rollback(
        self,
        strict_signature_policy,
        verified_signal,
    ):
        """Test that verified signature allows rollback."""
        rollback_callback = MagicMock(return_value=True)

        router = OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=strict_signature_policy,
        )

        result = await router.route_signal(verified_signal)

        assert result.success is True
        assert result.action == ActionType.ROLLBACK_ROUTE
        assert rollback_callback.called

    @pytest.mark.asyncio
    async def test_unverified_signature_blocks_rollback(
        self,
        strict_signature_policy,
        unverified_signal,
    ):
        """Test that unverified signature blocks rollback when required."""
        rollback_callback = MagicMock(return_value=True)

        router = OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=strict_signature_policy,
        )

        result = await router.route_signal(unverified_signal)

        assert result.success is False
        assert "signature" in result.message.lower() or "blocked" in result.message.lower()
        assert not rollback_callback.called

    @pytest.mark.asyncio
    async def test_no_signature_blocks_rollback_when_required(
        self,
        strict_signature_policy,
        no_signature_signal,
    ):
        """Test that missing signature blocks rollback when required."""
        rollback_callback = MagicMock(return_value=True)

        router = OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=strict_signature_policy,
        )

        result = await router.route_signal(no_signature_signal)

        assert result.success is False
        assert not rollback_callback.called

    @pytest.mark.asyncio
    async def test_unverified_signature_allowed_when_not_required(
        self,
        lax_signature_policy,
        unverified_signal,
    ):
        """Test that unverified signature is allowed when not required."""
        rollback_callback = MagicMock(return_value=True)

        router = OpsSignalRouter(
            on_rollback=rollback_callback,
            get_route_policy=lax_signature_policy,
        )

        result = await router.route_signal(unverified_signal)

        assert result.success is True
        assert rollback_callback.called

    @pytest.mark.asyncio
    async def test_signature_not_required_for_investigation(
        self,
        strict_signature_policy,
        unverified_signal,
    ):
        """Test that investigation doesn't require signature verification."""
        investigation_callback = MagicMock(return_value="inv_123")

        router = OpsSignalRouter(
            on_investigation=investigation_callback,
            get_route_policy=strict_signature_policy,
        )

        # Change signal type to drift (maps to investigation)
        signal = InboundOpsSignal(
            ts="2026-01-28T12:00:00Z",
            source=SignalSource.INORBIT,
            tenant_id="test-tenant",
            route_key="test-route",
            severity=Severity.WARN,  # WARN severity
            type=InboundSignalType.DRIFT_DETECTED,  # Maps to investigation
            payload=SignalPayload(raw={}),
            auth=AuthInfo(
                signature_present=True,
                verified=False,  # Not verified
            ),
            dedupe_key="test-drift",
        )

        result = await router.route_signal(signal)

        # Investigation should succeed even without verified signature
        # because it's not a critical automated action
        assert result.action == ActionType.OPEN_INVESTIGATION

    @pytest.mark.asyncio
    async def test_evidence_records_signature_block(
        self,
        strict_signature_policy,
        unverified_signal,
    ):
        """Test that blocked actions due to signature are recorded."""
        router = OpsSignalRouter(
            get_route_policy=strict_signature_policy,
        )

        await router.route_signal(unverified_signal)

        events = router.get_evidence_events()
        event_types = [e.event_type.value for e in events]

        assert "action_blocked_signature" in event_types
